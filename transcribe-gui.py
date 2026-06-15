"""
Auto Transcriber - Tkinter GUI for OpenAI Whisper.

Modernized Whisper GUI:
- safer dependency/runtime diagnostics
- CUDA-aware model loading
- FFmpeg preflight check
- robust SRT/VTT timestamp formatting
- optional multi-format output
- JSON and TSV export
- cached model reuse during a session
- basic progress bar and elapsed time
- clearer traceback logging
- native menu bar and improved gutters
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

APP_NAME = "Auto Transcriber"
APP_VERSION = "1.3"

# --- Dependency check -------------------------------------------------------
try:
    import whisper
    import torch
except ImportError as e:
    error_msg = (
        f"A required Python library was not found: {e.name}\n\n"
        "Run this app through transcribe-app.bat so the virtual environment loads correctly.\n\n"
        f"Python executable: {sys.executable}"
    )
    temp_root = tk.Tk()
    temp_root.withdraw()
    messagebox.showerror("Critical Error", error_msg)
    sys.exit(1)


# --- Formatting utilities --------------------------------------------------
def _milliseconds_total(seconds: float) -> int:
    """Return total milliseconds with carry-safe rounding."""
    return max(0, int(round(float(seconds) * 1000)))


def _split_milliseconds(seconds: float) -> tuple[int, int, int, int]:
    total_ms = _milliseconds_total(seconds)
    total_seconds, millis = divmod(total_ms, 1000)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return hours, minutes, secs, millis


def format_timestamp_srt(seconds: float) -> str:
    """Convert seconds to SRT timestamp: HH:MM:SS,mmm."""
    hours, minutes, secs, millis = _split_milliseconds(seconds)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_timestamp_vtt(seconds: float) -> str:
    """Convert seconds to VTT timestamp: HH:MM:SS.mmm."""
    hours, minutes, secs, millis = _split_milliseconds(seconds)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def _segment_text(seg: dict[str, Any]) -> str:
    return str(seg.get("text", "")).strip()


def segments_to_srt(result: dict[str, Any]) -> str:
    lines: list[str] = []
    for i, seg in enumerate(result.get("segments", []), start=1):
        start = format_timestamp_srt(seg.get("start", 0))
        end = format_timestamp_srt(seg.get("end", 0))
        text = _segment_text(seg)
        lines.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(lines).rstrip() + "\n"


def segments_to_vtt(result: dict[str, Any]) -> str:
    lines: list[str] = ["WEBVTT", ""]
    for i, seg in enumerate(result.get("segments", []), start=1):
        start = format_timestamp_vtt(seg.get("start", 0))
        end = format_timestamp_vtt(seg.get("end", 0))
        text = _segment_text(seg)
        lines.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(lines).rstrip() + "\n"


def segments_to_txt(result: dict[str, Any]) -> str:
    text = str(result.get("text", "")).strip()
    if text:
        return text + "\n"
    return "\n".join(_segment_text(seg) for seg in result.get("segments", [])).strip() + "\n"


def segments_to_timestamped_txt(result: dict[str, Any]) -> str:
    lines: list[str] = []
    for seg in result.get("segments", []):
        start = format_timestamp_vtt(seg.get("start", 0))
        end = format_timestamp_vtt(seg.get("end", 0))
        lines.append(f"[{start} - {end}] {_segment_text(seg)}")
    return "\n".join(lines).strip() + "\n"


def result_to_json(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2) + "\n"


def result_to_tsv(result: dict[str, Any]) -> str:
    lines = ["start\tend\ttext"]
    for seg in result.get("segments", []):
        start = format_timestamp_vtt(seg.get("start", 0))
        end = format_timestamp_vtt(seg.get("end", 0))
        text = _segment_text(seg).replace("\t", " ").replace("\r", " ").replace("\n", " ")
        lines.append(f"{start}\t{end}\t{text}")
    return "\n".join(lines).strip() + "\n"


FORMAT_MAP: dict[str, dict[str, Any]] = {
    "SRT (Subtitles)": {"ext": ".srt", "fn": segments_to_srt},
    "VTT (Web Subtitles)": {"ext": ".vtt", "fn": segments_to_vtt},
    "TXT (Plain Text)": {"ext": ".txt", "fn": segments_to_txt},
    "TXT + Timestamps": {"ext": ".timestamps.txt", "fn": segments_to_timestamped_txt},
    "JSON (Full Whisper Result)": {"ext": ".json", "fn": result_to_json},
    "TSV (Segments Table)": {"ext": ".tsv", "fn": result_to_tsv},
}

ALL_FORMATS_LABEL = "All Formats"


class StdoutRedirector:
    """Thread-safe stdout/stderr redirect into a Tkinter text widget."""

    def __init__(self, text_widget: tk.Text):
        self.text_widget = text_widget

    def write(self, string: str) -> None:
        if not string:
            return
        try:
            self.text_widget.after(0, self._append, string)
        except tk.TclError:
            pass

    def flush(self) -> None:
        pass

    def _append(self, string: str) -> None:
        try:
            self.text_widget.insert(tk.END, string)
            self.text_widget.see(tk.END)
        except tk.TclError:
            pass


class WhisperApp:
    MEDIA_TYPES = [
        ("Media files", "*.mp3 *.mp4 *.wav *.m4a *.mkv *.flac *.ogg *.webm *.aac *.wma *.mov *.avi"),
        ("All files", "*.*"),
    ]

    MODEL_OPTIONS = [
        ("Tiny (Fastest)", "tiny"),
        ("Base (Standard)", "base"),
        ("Small (Better)", "small"),
        ("Medium (Great)", "medium"),
        ("Large (Best - needs GPU)", "large"),
    ]

    COMMON_LANGUAGES = [
        ("Auto-Detect", None),
        ("English", "en"),
        ("Spanish", "es"),
        ("French", "fr"),
        ("German", "de"),
        ("Portuguese", "pt"),
        ("Italian", "it"),
        ("Japanese", "ja"),
        ("Korean", "ko"),
        ("Chinese", "zh"),
        ("Arabic", "ar"),
        ("Russian", "ru"),
        ("Hindi", "hi"),
    ]

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.minsize(900, 760)
        self.root.geometry("960x840")
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)

        self.selected_files: list[str] = []
        self.output_folder: str | None = None
        self.final_output_files: list[str] = []
        self.cancel_flag = threading.Event()
        self.is_running = False
        self.loaded_model_name: str | None = None
        self.loaded_model: Any | None = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.ffmpeg_path = shutil.which("ffmpeg")
        self.start_time = 0.0

        self._configure_style()
        self._build_menus()
        self._build_ui()
        self._run_startup_diagnostics()

    # ------------------------------------------------------------------ UI
    def _configure_style(self) -> None:
        """Apply a low-risk native ttk visual refresh."""
        self.style = ttk.Style(self.root)
        available = set(self.style.theme_names())
        if sys.platform.startswith("win") and "vista" in available:
            self.style.theme_use("vista")
        elif "clam" in available:
            self.style.theme_use("clam")

        default_font = ("Segoe UI", 10)
        title_font = ("Segoe UI", 18, "bold")
        small_font = ("Segoe UI", 9)
        button_font = ("Segoe UI", 10)

        self.root.option_add("*Font", default_font)
        self.style.configure("TFrame", padding=0)
        self.style.configure("Page.TFrame", padding=(18, 16, 18, 12))
        self.style.configure("TLabelFrame", padding=(12, 8, 12, 12))
        self.style.configure("TLabelFrame.Label", font=("Segoe UI", 10, "bold"))
        self.style.configure("Title.TLabel", font=title_font)
        self.style.configure("Muted.TLabel", font=small_font)
        self.style.configure("Status.TLabel", font=small_font)
        self.style.configure("TButton", font=button_font, padding=(10, 5))
        self.style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(14, 7))
        self.style.configure("Danger.TButton", font=("Segoe UI", 10, "bold"), padding=(10, 7))
        self.style.configure("Horizontal.TProgressbar", thickness=12)

    def _build_menus(self) -> None:
        """Build a small native menu bar for common app actions."""
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Browse Files...", command=self.browse_files, accelerator="Ctrl+O")
        file_menu.add_command(label="Select Destination...", command=self.browse_output, accelerator="Ctrl+D")
        file_menu.add_separator()
        file_menu.add_command(label="Open Save Location", command=self.open_save_location)
        file_menu.add_separator()
        file_menu.add_command(label="Close App", command=self.close_app, accelerator="Ctrl+Q")
        menubar.add_cascade(label="File", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="Copy Diagnostics", command=self.copy_diagnostics)
        help_menu.add_separator()
        help_menu.add_command(label="About Auto Transcriber", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)
        self.root.bind_all("<Control-o>", lambda _event: self.browse_files())
        self.root.bind_all("<Control-d>", lambda _event: self.browse_output())
        self.root.bind_all("<Control-q>", lambda _event: self.close_app())

    def show_about(self) -> None:
        """Show a compact about dialog with runtime details."""
        gpu_line = "CUDA unavailable"
        if torch.cuda.is_available():
            try:
                props = torch.cuda.get_device_properties(0)
                total = getattr(props, "total_memory", getattr(props, "total_mem", 0))
                vram = total / (1024 ** 3) if total else 0
                gpu_line = f"{torch.cuda.get_device_name(0)} ({vram:.1f} GB VRAM)"
            except Exception:
                gpu_line = "CUDA available; GPU details unavailable"

        messagebox.showinfo(
            f"About {APP_NAME}",
            "\n".join([
                f"{APP_NAME} {APP_VERSION}",
                "Whisper transcription utility with GPU diagnostics and subtitle export.",
                "",
                f"Python: {sys.version.split()[0]}",
                f"Whisper: {getattr(whisper, '__version__', 'installed')}",
                f"Torch: {torch.__version__}",
                f"Torch CUDA build: {torch.version.cuda or 'none'}",
                f"GPU: {gpu_line}",
                f"FFmpeg: {self.ffmpeg_path or 'not found'}",
            ]),
        )

    def close_app(self) -> None:
        """Close the app, with a warning if a transcription is in progress."""
        if self.is_running:
            should_close = messagebox.askyesno(
                "Close Auto Transcriber?",
                "A transcription is currently running. Close the app anyway?",
            )
            if not should_close:
                return
        self.root.destroy()

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main = ttk.Frame(self.root, style="Page.TFrame")
        main.grid(row=0, column=0, sticky="nsew", padx=18, pady=16)
        main.columnconfigure(0, weight=1)
        main.rowconfigure(6, weight=1)

        # Header
        header = ttk.Frame(main)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        header.columnconfigure(0, weight=1)

        ttk.Label(header, text=APP_NAME, style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(
            header,
            text="Whisper transcription utility with GPU diagnostics and subtitle export.",
            style="Muted.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 0))

        # Media selection
        media_frame = ttk.LabelFrame(main, text="1. Media files")
        media_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        media_frame.columnconfigure(1, weight=1)

        self.btn_browse = ttk.Button(media_frame, text="Browse files", command=self.browse_files)
        self.btn_browse.grid(row=0, column=0, sticky="w", padx=(10, 12), pady=10)

        self.lbl_file = ttk.Label(media_frame, text="No files selected", style="Muted.TLabel", anchor="w")
        self.lbl_file.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=10)

        # Output folder
        out_frame = ttk.LabelFrame(main, text="2. Output folder")
        out_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        out_frame.columnconfigure(1, weight=1)

        self.btn_out = ttk.Button(out_frame, text="Select destination", command=self.browse_output)
        self.btn_out.grid(row=0, column=0, sticky="w", padx=(10, 12), pady=10)

        self.lbl_out = ttk.Label(out_frame, text="Default: same folder as each source file", style="Muted.TLabel", anchor="w")
        self.lbl_out.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=10)

        # Settings
        settings_frame = ttk.LabelFrame(main, text="3. Transcription settings")
        settings_frame.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        settings_frame.columnconfigure(1, weight=1)
        settings_frame.columnconfigure(3, weight=1)

        ttk.Label(settings_frame, text="Model").grid(row=0, column=0, sticky="nw", padx=(10, 8), pady=(10, 8))
        model_row = ttk.Frame(settings_frame)
        model_row.grid(row=0, column=1, columnspan=3, sticky="ew", padx=(0, 10), pady=(10, 8))

        self.model_var = tk.StringVar(value="base")
        for i, (text, mode) in enumerate(self.MODEL_OPTIONS):
            ttk.Radiobutton(model_row, text=text, variable=self.model_var, value=mode).grid(row=0, column=i, sticky="w", padx=(0, 12))

        ttk.Label(settings_frame, text="Language").grid(row=1, column=0, sticky="w", padx=(10, 8), pady=6)
        self.lang_var = tk.StringVar(value="Auto-Detect")
        lang_names = [name for name, _ in self.COMMON_LANGUAGES]
        self.lang_combo = ttk.Combobox(settings_frame, textvariable=self.lang_var, values=lang_names, state="readonly", width=18)
        self.lang_combo.grid(row=1, column=1, sticky="w", pady=6)

        ttk.Label(settings_frame, text="Output").grid(row=1, column=2, sticky="w", padx=(20, 8), pady=6)
        self.format_var = tk.StringVar(value="SRT (Subtitles)")
        fmt_names = list(FORMAT_MAP.keys()) + [ALL_FORMATS_LABEL]
        self.fmt_combo = ttk.Combobox(settings_frame, textvariable=self.format_var, values=fmt_names, state="readonly", width=26)
        self.fmt_combo.grid(row=1, column=3, sticky="w", padx=(0, 10), pady=6)

        ttk.Label(settings_frame, text="Mode").grid(row=2, column=0, sticky="w", padx=(10, 8), pady=6)
        mode_row = ttk.Frame(settings_frame)
        mode_row.grid(row=2, column=1, columnspan=3, sticky="ew", padx=(0, 10), pady=6)
        self.task_var = tk.StringVar(value="transcribe")
        ttk.Radiobutton(mode_row, text="Transcribe original language", variable=self.task_var, value="transcribe").grid(row=0, column=0, sticky="w", padx=(0, 18))
        ttk.Radiobutton(mode_row, text="Translate to English", variable=self.task_var, value="translate").grid(row=0, column=1, sticky="w")

        ttk.Label(settings_frame, text="Prompt").grid(row=3, column=0, sticky="w", padx=(10, 8), pady=(8, 0))
        self.prompt_var = tk.StringVar(value="")
        self.prompt_entry = ttk.Entry(settings_frame, textvariable=self.prompt_var)
        self.prompt_entry.grid(row=3, column=1, columnspan=3, sticky="ew", padx=(0, 10), pady=(8, 0))

        ttk.Label(
            settings_frame,
            text="Optional vocabulary/context hint, such as names, acronyms, or specialized terms.",
            style="Muted.TLabel",
        ).grid(row=4, column=1, columnspan=3, sticky="w", padx=(0, 10), pady=(3, 10))

        # Progress and status
        progress_frame = ttk.Frame(main)
        progress_frame.grid(row=4, column=0, sticky="ew", pady=(8, 6))
        progress_frame.columnconfigure(0, weight=1)

        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.grid(row=0, column=0, sticky="ew")

        self.status_var = tk.StringVar(value="Ready.")
        self.status_label = ttk.Label(progress_frame, textvariable=self.status_var, style="Status.TLabel", anchor="w")
        self.status_label.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        # Actions
        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=5, column=0, sticky="ew", pady=(4, 10))
        btn_frame.columnconfigure(5, weight=1)

        self.btn_run = ttk.Button(btn_frame, text="Start transcription", command=self.start_thread, style="Primary.TButton")
        self.btn_run.grid(row=0, column=0, sticky="w", padx=(0, 8))

        self.btn_cancel = ttk.Button(btn_frame, text="Cancel", command=self.request_cancel, state="disabled")
        self.btn_cancel.grid(row=0, column=1, sticky="w", padx=(0, 8))

        self.btn_open = ttk.Button(btn_frame, text="Open save location", command=self.open_save_location, state="disabled")
        self.btn_open.grid(row=0, column=2, sticky="w", padx=(0, 8))

        self.btn_diag = ttk.Button(btn_frame, text="Copy diagnostics", command=self.copy_diagnostics)
        self.btn_diag.grid(row=0, column=3, sticky="w", padx=(0, 8))

        self.btn_quit = ttk.Button(btn_frame, text="Exit", command=self.close_app, style="Danger.TButton")
        self.btn_quit.grid(row=0, column=6, sticky="e")

        # Log
        log_frame = ttk.LabelFrame(main, text="Log")
        log_frame.grid(row=6, column=0, sticky="nsew", pady=(0, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_area = scrolledtext.ScrolledText(
            log_frame,
            height=16,
            wrap="word",
            borderwidth=1,
            relief="solid",
            padx=8,
            pady=6,
        )
        self.log_area.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.log(f"{APP_NAME} {APP_VERSION} ready.")

    # ------------------------------------------------------------------ Diagnostics
    def _run_startup_diagnostics(self) -> None:
        self.log("Startup diagnostics:")
        self.log(f"  Python: {sys.version.split()[0]} ({sys.executable})")
        self.log(f"  Whisper: {getattr(whisper, '__version__', 'installed')}")
        self.log(f"  Torch: {torch.__version__}")
        self.log(f"  Torch CUDA build: {torch.version.cuda or 'none'}")

        if self.ffmpeg_path:
            self.log(f"  FFmpeg: {self.ffmpeg_path}")
        else:
            self.log("  FFmpeg: NOT FOUND. Media decoding will fail until ffmpeg is on PATH.")

        self._detect_hardware()

    def _detect_hardware(self) -> None:
        try:
            cuda_available = torch.cuda.is_available()
            if cuda_available:
                gpu_name = torch.cuda.get_device_name(0)
                props = torch.cuda.get_device_properties(0)
                total = getattr(props, "total_memory", getattr(props, "total_mem", 0))
                vram = total / (1024 ** 3) if total else 0
                self.device = "cuda"
                self.log(f"  GPU: {gpu_name} ({vram:.1f} GB VRAM). CUDA acceleration enabled.")
            else:
                self.device = "cpu"
                self.log("  GPU: CUDA unavailable. Whisper will run on CPU.")
                if "+cpu" in torch.__version__.lower() or not torch.version.cuda:
                    self.log("  Note: This looks like a CPU-only PyTorch install.")
        except Exception as e:
            self.device = "cpu"
            self.log(f"  GPU diagnostic failed: {e}")

    def _diagnostics_text(self) -> str:
        ffmpeg_version = "not found"
        if self.ffmpeg_path:
            try:
                proc = subprocess.run([self.ffmpeg_path, "-version"], capture_output=True, text=True, timeout=5)
                ffmpeg_version = proc.stdout.splitlines()[0] if proc.stdout else "found"
            except Exception as e:
                ffmpeg_version = f"found, but version check failed: {e}"

        gpu_text = "CUDA unavailable"
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            total = getattr(props, "total_memory", getattr(props, "total_mem", 0))
            vram = total / (1024 ** 3) if total else 0
            gpu_text = f"{torch.cuda.get_device_name(0)} ({vram:.1f} GB VRAM)"

        return "\n".join([
            f"{APP_NAME} {APP_VERSION}",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            f"Python: {sys.version}",
            f"Executable: {sys.executable}",
            f"Whisper: {getattr(whisper, '__version__', 'installed')}",
            f"Torch: {torch.__version__}",
            f"Torch CUDA build: {torch.version.cuda or 'none'}",
            f"torch.cuda.is_available(): {torch.cuda.is_available()}",
            f"GPU: {gpu_text}",
            f"FFmpeg: {ffmpeg_version}",
            f"PATH ffmpeg: {self.ffmpeg_path or 'not found'}",
        ])

    def copy_diagnostics(self) -> None:
        text = self._diagnostics_text()
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status_var.set("Diagnostics copied to clipboard.")
        self.log("Diagnostics copied to clipboard.")

    # ------------------------------------------------------------------ File browsing
    def browse_files(self) -> None:
        filenames = filedialog.askopenfilenames(filetypes=self.MEDIA_TYPES)
        if not filenames:
            return
        self.selected_files = list(filenames)
        count = len(self.selected_files)
        display = os.path.basename(self.selected_files[0]) if count == 1 else f"{count} files selected"
        self.lbl_file.config(text=display)
        self.btn_open.config(state="disabled")
        self.final_output_files = []
        self.progress_var.set(0)
        for f in self.selected_files:
            self.log(f"Queued: {f}")

    def browse_output(self) -> None:
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder = folder
            self.lbl_out.config(text=folder)
            self.log(f"Output folder: {folder}")

    # ------------------------------------------------------------------ Logging/state
    def log(self, message: str) -> None:
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)

    def _set_status(self, message: str) -> None:
        self.root.after(0, lambda: self.status_var.set(message))

    def _set_progress(self, current: int, total: int) -> None:
        percent = 0 if total <= 0 else (current / total) * 100
        self.root.after(0, lambda: self.progress_var.set(percent))

    def _set_running_state(self, running: bool) -> None:
        if running:
            self.btn_run.config(state="disabled", text="Running...")
            self.btn_cancel.config(state="normal")
            self.btn_open.config(state="disabled")
            self.btn_browse.config(state="disabled")
            self.btn_out.config(state="disabled")
            self.fmt_combo.config(state="disabled")
            self.lang_combo.config(state="disabled")
            self.prompt_entry.config(state="disabled")
        else:
            self.btn_run.config(state="normal", text="Start Transcription")
            self.btn_cancel.config(state="disabled")
            self.btn_browse.config(state="normal")
            self.btn_out.config(state="normal")
            self.fmt_combo.config(state="readonly")
            self.lang_combo.config(state="readonly")
            self.prompt_entry.config(state="normal")
            self.is_running = False

    # ------------------------------------------------------------------ Transcription
    def start_thread(self) -> None:
        if not self.selected_files:
            messagebox.showwarning("Error", "Please select at least one file first.")
            return
        if not self.ffmpeg_path:
            messagebox.showerror("FFmpeg Not Found", "FFmpeg was not found on PATH. Whisper cannot decode most media files until FFmpeg is installed and available on PATH.")
            return

        self.cancel_flag.clear()
        self.is_running = True
        self.final_output_files = []
        self.progress_var.set(0)
        self.start_time = time.time()
        self._set_running_state(True)
        threading.Thread(target=self.run_transcription, daemon=True).start()

    def request_cancel(self) -> None:
        if self.is_running:
            self.cancel_flag.set()
            self.log("\n*** CANCEL REQUESTED — current file must finish before stopping. ***")
            self._set_status("Cancel requested. Waiting for current file to finish...")

    def _language_code(self) -> str | None:
        selected = self.lang_var.get()
        return dict(self.COMMON_LANGUAGES).get(selected)

    def _selected_formats(self) -> list[dict[str, Any]]:
        selected = self.format_var.get()
        if selected == ALL_FORMATS_LABEL:
            return list(FORMAT_MAP.values())
        return [FORMAT_MAP[selected]]

    def _get_model(self, model_name: str) -> Any:
        if self.loaded_model is not None and self.loaded_model_name == model_name:
            print(f"Using cached Whisper model '{model_name}' on {self.device}.")
            return self.loaded_model

        print(f"Loading Whisper model '{model_name}' on {self.device}... (this may take a moment)")
        self.loaded_model = whisper.load_model(model_name, device=self.device)
        self.loaded_model_name = model_name
        return self.loaded_model

    @staticmethod
    def _unique_output_path(save_dir: str, stem: str, ext: str) -> str:
        out_path = os.path.join(save_dir, f"{stem}{ext}")
        counter = 1
        while os.path.exists(out_path):
            out_path = os.path.join(save_dir, f"{stem} ({counter}){ext}")
            counter += 1
        return out_path

    def run_transcription(self) -> None:
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        try:
            redirector = StdoutRedirector(self.log_area)
            sys.stdout = redirector
            sys.stderr = redirector

            model_name = self.model_var.get()
            model = self._get_model(model_name)
            lang_code = self._language_code()
            formats = self._selected_formats()

            total = len(self.selected_files)
            completed_files = 0

            for idx, filepath in enumerate(self.selected_files, start=1):
                if self.cancel_flag.is_set():
                    print(f"\nCancelled. {completed_files} of {total} files completed.")
                    break

                basename = os.path.basename(filepath)
                self._set_status(f"Transcribing {idx}/{total}: {basename}")
                self._set_progress(idx - 1, total)
                print(f"\n[{idx}/{total}] Transcribing: {basename}")
                print("-" * 60)

                kwargs: dict[str, Any] = {
                    "verbose": True,
                    "task": self.task_var.get(),
                    "fp16": self.device == "cuda",
                }
                if lang_code:
                    kwargs["language"] = lang_code

                initial_prompt = self.prompt_var.get().strip()
                if initial_prompt:
                    kwargs["initial_prompt"] = initial_prompt

                result = model.transcribe(filepath, **kwargs)

                if self.cancel_flag.is_set():
                    print(f"Cancelled after current file: {basename}")
                    break

                stem = os.path.splitext(basename)[0]
                save_dir = self.output_folder or os.path.dirname(filepath)
                Path(save_dir).mkdir(parents=True, exist_ok=True)

                for fmt in formats:
                    out_path = self._unique_output_path(save_dir, stem, fmt["ext"])
                    content = fmt["fn"](result)
                    with open(out_path, "w", encoding="utf-8", newline="") as f:
                        f.write(content)
                    print(f"Saved: {out_path}")
                    self.final_output_files.append(out_path)

                completed_files += 1
                self._set_progress(completed_files, total)

            elapsed = time.time() - self.start_time
            count = len(self.final_output_files)
            if count > 0:
                print(f"\n{'=' * 60}")
                print(f"Completed: {completed_files} media file(s), {count} output file(s), elapsed {elapsed:.1f}s.")
                self.root.after(0, self._enable_open_button)
                if count == 1:
                    self.root.after(0, lambda: messagebox.showinfo("Done", f"Saved:\n{self.final_output_files[0]}"))
                else:
                    self.root.after(0, lambda: messagebox.showinfo("Done", f"{count} output files created."))
                self._set_status(f"Done. {count} output file(s) created in {elapsed:.1f}s.")
            else:
                print("\nNo files were transcribed.")
                self._set_status("No files were transcribed.")

        except Exception as e:
            tb = traceback.format_exc()
            print(f"\nERROR: {e}\n\n{tb}")
            self._write_error_log(tb)
            self.root.after(0, lambda: messagebox.showerror("Error", f"{e}\n\nA detailed traceback was written to whisper-last-error.log."))
            self._set_status("Error. See log.")
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            self.root.after(0, lambda: self._set_running_state(False))

    def _write_error_log(self, traceback_text: str) -> None:
        try:
            app_dir = Path(__file__).resolve().parent
            log_path = app_dir / "whisper-last-error.log"
            log_path.write_text(self._diagnostics_text() + "\n\n" + traceback_text, encoding="utf-8")
        except Exception:
            pass

    def _enable_open_button(self) -> None:
        self.btn_open.config(state="normal")

    # ------------------------------------------------------------------ Open save location
    def open_save_location(self) -> None:
        if not self.final_output_files:
            return
        target = self.final_output_files[-1]
        if os.path.exists(target):
            subprocess.run(["explorer", "/select,", os.path.normpath(target)])
            return
        folder = os.path.dirname(target)
        if os.path.isdir(folder):
            subprocess.run(["explorer", os.path.normpath(folder)])


if __name__ == "__main__":
    root = tk.Tk()
    app = WhisperApp(root)
    root.mainloop()
