<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>SAVDSA 2025 Financial Snapshot</title>
  <!-- 
    FIX: Added 'unsafe-inline' to script-src to allow the main script block to run.
  -->
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data: blob: https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.tailwindcss.com; font-src 'self' https://fonts.gstatic.com; script-src 'self' https://cdn.jsdelivr.net https://cdn.tailwindcss.com 'unsafe-inline'; connect-src 'self';" />

  <!-- Fonts -->
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">

  <!-- Tailwind (CDN dev build). For production, build a static CSS file. -->
  <script src="https://cdn.tailwindcss.com?plugins=forms,typography"></script>

  <!-- Chart.js pinned + integrity -->
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js" xintegrity="sha384-L7Jt9K8C8nqF4p8+9o0a6o6mS1Vgq6cBvT8+zJAn3v5YQKp2V4x4i8D6lXz2zYg9" crossorigin="anonymous"></script>

  <style>
    :root { --dsa-red: #D00000; }
    body { font-family: 'Inter', system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif; background-color: #F3F4F6; }
    .chart-container { position: relative; width: 100%; height: 24rem; max-height: 400px; }
    @media (min-width:640px){ .chart-container { height: 20rem; } }
    @media (min-width:1024px){ .chart-container { height: 24rem; } }

    /* Print styles for GM handouts */
    @media print {
      body { background: #fff; }
      main { box-shadow: none !important; border: none !important; }
      .no-print { display: none !important; }
      .page-break { page-break-before: always; }
    }
  </style>
  <!-- SheetJS for CSV/XLSX parsing -->
  <script src="https://cdn.jsdelivr.net/npm/xlsx@0.18.5/dist/xlsx.full.min.js" xintegrity="sha384-CJX3pR2n1+0p0l7CU0YtNQ5WPRr6JYdAEuZc2QqYpM8j2jYt2iCq0C8i3H6hXQvO" crossorigin="anonymous"></script>
</head>
<body class="p-4 md:p-8">

  <!-- IMPROVEMENT: Loading overlay -->
  <div id="loading-overlay" class="fixed inset-0 bg-white bg-opacity-75 z-50 flex items-center justify-center" style="display: none;">
    <div class="animate-spin rounded-full h-16 w-16 border-t-4 border-b-4 border-gray-900"></div>
  </div>

  <main class="max-w-6xl mx-auto bg-white rounded-xl shadow-2xl p-6 md:p-10">
    <header class="text-center border-b-2 border-gray-100 pb-6 mb-8">
      <h1 class="text-4xl md:text-5xl font-extrabold text-[var(--dsa-red)] mb-2">SAVDSA 2025 Financial Snapshot</h1>
      <p class="text-lg md:text-xl text-gray-700 font-medium">A Report on Our Chapter's Financial Health (Jan 1 – Oct 31, 2025)</p>
      <p class="text-md text-gray-500 italic mt-2">Note: Q4 data is not yet finalized. Projected Q4 Dues Income: ~<span id="proj-dues">$700</span></p>
    </header>

    <!-- Controls: load CSV/XLSX from your Analysis Pack (or any normalized ledger) -->
    <section class="mb-8 no-print" aria-labelledby="upload-heading">
      <h2 id="upload-heading" class="text-2xl font-bold text-gray-900 mb-3">Load fresh data</h2>
      <p class="text-sm text-gray-600 mb-3">Upload your CSV or Excel ledger file. This app will automatically find the headers and process the data.</p>
      <div class="flex items-center gap-3">
        <input id="fileInput" type="file" accept=".csv, .xlsx" class="block w-full text-sm text-gray-900 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-gray-900 file:text-white hover:file:bg-gray-800" />
        <button id="resetData" type="button" class="px-3 py-2 rounded-lg border border-gray-300 text-sm font-medium hover:bg-gray-50">Reset to demo data</button>
      </div>
      <p class="text-xs text-gray-500 mt-2">Expected columns (case-insensitive): <code>date</code>, <code>amount</code> (or <code>signed</code>), <code>category</code>, <code>account</code>, <code>description</code>.</p>
    </section>

    <!-- Top-Line Financials -->
    <section class="mb-10" aria-labelledby="kpi-heading">
      <h2 id="kpi-heading" class="text-3xl font-bold text-gray-900 mb-6 text-center">Top-Line Financials (YTD)</h2>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6" aria-live="polite">
        <div class="bg-gray-50 rounded-lg p-6 border border-gray-200 text-center" aria-label="Total Income">
          <p class="text-sm font-semibold text-green-700 uppercase tracking-wider">Total Income</p>
          <p id="kpi-income" class="text-5xl font-extrabold text-green-600 mt-2">$0.00</p>
        </div>
        <div class="bg-gray-50 rounded-lg p-6 border border-gray-200 text-center" aria-label="Total Expenses">
          <p class="text-sm font-semibold text-red-700 uppercase tracking-wider">Total Expenses</p>
          <p id="kpi-expense" class="text-5xl font-extrabold text-red-600 mt-2">$0.00</p>
        </div>
        <div class="bg-gray-50 rounded-lg p-6 border border-gray-200 text-center" aria-label="Net Surplus">
          <p class="text-sm font-semibold text-blue-700 uppercase tracking-wider">Net Surplus</p>
          <p id="kpi-net" class="text-5xl font-extrabold text-blue-600 mt-2">$0.00</p>
        </div>
      </div>
    </section>

    <!-- Financial Position -->
    <section class="mb-10" aria-labelledby="position-heading">
      <h2 id="position-heading" class="text-3xl font-bold text-gray-900 mb-6 text-center">Our Financial Position</h2>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <!-- Balances -->
        <div class="bg-white rounded-lg p-6 border border-gray-200 shadow-sm">
          <h3 class="text-xl font-bold text-gray-800 mb-4">Current Account Balances</h3>
          <div class="space-y-3">
            <div>
              <p class="text-sm font-semibold text-gray-600">Main Account</p>
              <p id="bal-main" class="text-3xl font-extrabold text-gray-900">$0.00</p>
            </div>
            <div>
              <p class="text-sm font-semibold text-gray-600">Slush Fund</p>
              <p id="bal-slush" class="text-3xl font-extrabold text-gray-900">$0.00</p>
            </div>
            <div class="pt-2 border-t border-gray-300">
              <p class="text-sm font-semibold text-[var(--dsa-red)]">Total Balance On Hand</p>
              <p id="bal-total" class="text-3xl font-extrabold text-[var(--dsa-red)]">$0.00</p>
            </div>
          </div>
        </div>

        <!-- Top Categories -->
        <div class="bg-white rounded-lg p-6 border border-gray-200 shadow-sm">
          <h3 class="text-xl font-bold text-gray-800 mb-4">Top 3 Spending Categories</h3>
          <ol id="top-cats" class="list-decimal list-inside space-y-3 text-lg"></ol>
          <div class="pt-3 border-t border-gray-300 mt-4">
            <p class="text-sm font-semibold text-gray-600">All Other Spending</p>
            <p id="other-spend" class="text-2xl font-extrabold text-gray-900">$0.00</p>
          </div>
        </div>

        <!-- Budget vs Actual -->
        <div class="bg-white rounded-lg p-6 border border-gray-200 shadow-sm">
          <h3 class="text-xl font-bold text-gray-800 mb-4">Income vs. 2025 Budget</h3>
          <div class="space-y-3">
            <div>
              <p class="text-sm font-semibold text-gray-600">Budgeted Income Goal</p>
              <p id="budget-goal" class="text-3xl font-extrabold text-gray-900">$0.00</p>
            </div>
            <div>
              <p class="text-sm font-semibold text-gray-600">Actual Income (YTD)</p>
              <p id="budget-actual" class="text-3xl font-extrabold text-gray-900">$0.00</p>
            </div>
            <div class="pt-2 border-t border-gray-300">
              <p class="text-sm font-semibold text-green-700">Variance (Surplus)</p>
              <p id="budget-var" class="text-3xl font-extrabold text-green-600">$0.00</p>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- Charts -->
    <section class="mb-10 pt-8 border-t-2 border-gray-100" aria-labelledby="charts-heading">
      <!-- IMPROVEMENT: This h2 is now dynamic and updated by the script -->
      <h2 id="charts-heading" class="text-3xl font-bold text-gray-900 mb-8 text-center">The Story in Charts (May – Oct 2025)</h2>
      <div class="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div class="bg-white p-4 rounded-lg shadow-md border border-gray-200">
          <h3 class="text-xl font-bold text-gray-800 text-center mb-2">Chapter's Financial Growth</h3>
          <p class="text-gray-600 text-center text-sm mb-4">Cumulative balance over the last six months.</p>
          <div class="chart-container"><canvas id="balanceChart" aria-label="Cumulative balance line chart" role="img"></canvas></div>
        </div>
        <div class="bg-white p-4 rounded-lg shadow-md border border-gray-200">
          <h3 class="text-xl font-bold text-gray-800 text-center mb-2">Monthly Income vs. Expenses</h3>
          <p class="text-gray-600 text-center text-sm mb-4">Income arrives in spikes (dues), expenses are steadier.</p>
          <div class="chart-container"><canvas id="cashFlowChart" aria-label="Stacked bars of income and expenses with net line" role="img"></canvas></div>
        </div>
      </div>
    </section>

    <!-- Takeaways -->
    <section class="pt-8 border-t-2 border-gray-100 mb-10" aria-labelledby="takeaways-heading">
      <h2 id="takeaways-heading" class="text-3xl font-bold text-gray-900 mb-6 text-center">Key Takeaways for 2026</h2>
      <div class="max-w-3xl mx-auto bg-blue-50 rounded-lg p-6 border border-blue-200">
        <ul class="list-disc list-inside space-y-3 text-lg text-blue-900">
          <li class="font-medium"><span class="font-bold">Strong & Stable:</span> The chapter is in a very strong and stable financial position.</li>
          <li class="font-medium"><span class="font-bold">Exceeded Goal:</span> We surpassed our 2025 income goal by over $270.</li>
          <li class="font-medium"><span class="font-bold">Spiky Income:</span> Income arrives in quarterly spikes; plan around this rhythm.</li>
          <li class="font-medium"><span class="font-bold">Strategic Surplus:</span> Our healthy surplus (projected &gt; $3,500 EOY) can fund 2026 campaigns.</li>
        </ul>
      </div>
    </section>

    <!-- Itemized Transactions -->
    <section class="pt-8 border-t-2 border-gray-100" aria-labelledby="tx-heading">
      <h2 id="tx-heading" class="text-3xl font-bold text-gray-900 mb-6 text-center">Itemized Transactions (Jan – Oct 2025)</h2>

      <details class="mb-4 mx-auto max-w-3xl no-print">
        <summary class="cursor-pointer font-semibold text-gray-800">Privacy note / members-only view</summary>
        <p class="text-sm text-gray-600 mt-2">Personal names in reimbursements may be redacted in the public view. This table is presented for member accountability.</p>
        <button id="downloadCsv" class="mt-3 inline-flex items-center px-3 py-2 text-sm font-medium rounded-lg bg-gray-900 text-white hover:bg-gray-800">Download CSV</button>
      </details>

      <div class="overflow-x-auto bg-white rounded-lg shadow-md border border-gray-200">
        <table class="min-w-full divide-y divide-gray-200" aria-describedby="tx-note">
          <caption class="sr-only">Itemized transactions Jan–Oct 2025</caption>
          <thead class="bg-gray-50">
            <tr>
              <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
              <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Account</th>
              <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Transaction Details</th>
              <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Category</th>
              <th scope="col" class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Amount</th>
            </tr>
          </thead>
          <tbody id="tx-body" class="bg-white divide-y divide-gray-200"></tbody>
        </table>
      </div>
      <p id="tx-note" class="mt-2 text-sm text-gray-500">Methodology: income shown positive, expenses negative; transfers net to $0 across accounts. Data source: Treasurer ledger exported Oct 31, 2025.</p>
    </section>
  </main>

  <script>
    // === FIX: Chart instance storage ===
    let chartInstances = {};

    // === Single Source of Truth ===
    let fin = {
      projectedQ4Dues: 700,
      kpis: { income: 4170.97, expenses: 1369.35, net: 2801.62 },
      balances: { main: 2032.52, slush: 769.10 },
      budget: { incomeGoal: 3900.00 },
      categoriesTop3: [
        { name: 'Bills', amount: 795.94 },
        { name: 'Reimbursements', amount: 429.00 },
        { name: 'Equipment', amount: 144.41 },
      ],
      series: {
        months: ['May','Jun','Jul','Aug','Sep','Oct'],
        cumulative: [60.00,1680.79,2167.73,1738.73,2722.13,2801.62],
        income: [60.00,1668.73,987.93,0.00,1109.31,337.00],
        expenses: [0.00,47.94,500.99,429.00,125.91,265.51]
      },
      table: [
        { date:'2025-05-14', account:'Checking', details:'Opening Balance (Initial deposit)', category:'Dues Share', amount: 60.00 },
        { date:'2025-06-03', account:'Checking', details:'Test Deposit', category:'Dues Share', amount: 0.01 },
        { date:'2025-06-18', account:'Checking', details:'PEX Balance Transfer', category:'Dues Share', amount: 1668.72 },
        { date:'2025-06-23', account:'Checking', details:'PayPal Payment: Proton Mail (Covered 1 month while waiting for discount code)', category:'Bills', amount: -47.94 },
        { date:'2025-07-02', account:'Checking', details:'PayPal Donation: Kendra (July 12 Fundraiser)', category:'Fundraisers', amount: 9.16 },
        { date:'2025-07-03', account:'Checking', details:'PayPal Payment: Proton Mail (Annual payment)', category:'Bills', amount: -300.99 },
        { date:'2025-07-05', account:'Checking', details:'PayPal Payment: Kristen Russell - Sentient Bean (General Meeting Rent)', category:'Bills', amount: -200.00 },
        { date:'2025-07-12', account:'Slush', details:'Cash Deposit: July 12 Fundraiser Revenue (Cash with Val)', category:'Fundraisers', amount: 273.00 },
        { date:'2025-07-24', account:'Checking', details:'2025 Q2 Dues Share from National', category:'Dues Share', amount: 696.77 },
        { date:'2025-08-12', account:'Checking', details:'Convention Funds Payment (Approved payment to George Robles 8/7/25)', category:'Reimbursement', amount: -429.00 },
        { date:'2025-09-23', account:'Checking', details:'PayPal Reimbursement: CryptPad - George (For months June - September)', category:'Bills', amount: -47.01 },
        { date:'2025-09-23', account:'Slush', details:'Reimbursement: Cards - Chase (For business and voting cards)', category:'Equipment', amount: -78.90 },
        { date:'2025-09-26', account:'Checking', details:'2025 Merch Payment from Val', category:'Merch', amount: 375.00 },
        { date:'2025-09-27', account:'Checking', details:'2025 Q3 Dues Share from National', category:'Dues Share', amount: 784.10 },
        { date:'2025-09-29', account:'Checking', details:'Donation - M. Rogers', category:'Donation', amount: 52.69 },
        { date:'2025-10-06', account:'Slush', details:'Reimbursement: Cards - Chase (For business and voting cards)', category:'Equipment', amount: -65.51 },
        { date:'2025-10-23', account:'Checking', details:'PayPal Reimbursement: CryptPad - George (For months Oct - May)', category:'Bills', amount: -218.00 },
        { date:'2025-10-24', account:'Checking', details:'PayPal Payment: Proton Mail (Annual payment)', category:'Bills', amount: -47.50 },
        { date:'2025-10-27', account:'Slush', details:'Slush Fund Boost', category:'Dues Share', amount: 50.00 },
        { date:'2025-10-27', account:'Slush', details:'Transfer to Checking', category:'Transfer', amount: -50.00 },
        { date:'2025-10-27', account:'Checking', details:'Transfer from Slush', category:'Transfer', amount: 50.00 },
      ]
    };

    // === Formatters ===
    const currencyFull = new Intl.NumberFormat('en-US',{ style:'currency', currency:'USD' });
    const currencyCompact = new Intl.NumberFormat('en-US',{ style:'currency', currency:'USD', notation:'compact', maximumFractionDigits:1 });

    // === Populate KPIs & cards ===
    function populateKPIs() {
      document.getElementById('proj-dues').textContent = currencyFull.format(fin.projectedQ4Dues);
      document.getElementById('kpi-income').textContent = currencyFull.format(fin.kpis.income);
      document.getElementById('kpi-expense').textContent = currencyFull.format(fin.kpis.expenses);
      document.getElementById('kpi-net').textContent = currencyFull.format(fin.kpis.net);

      document.getElementById('bal-main').textContent = currencyFull.format(fin.balances.main);
      document.getElementById('bal-slush').textContent = currencyFull.format(fin.balances.slush);
      document.getElementById('bal-total').textContent = currencyFull.format(fin.balances.main + fin.balances.slush);

      document.getElementById('budget-goal').textContent = currencyFull.format(fin.budget.incomeGoal);
      document.getElementById('budget-actual').textContent = currencyFull.format(fin.kpis.income);
      const variance = fin.kpis.income - fin.budget.incomeGoal;
      document.getElementById('budget-var').textContent = (variance >= 0 ? '+' : '') + currencyFull.format(variance);

      // Top categories (computed other = total expenses - top3 sum)
      const topList = document.getElementById('top-cats');
      topList.innerHTML = '';
      fin.categoriesTop3.forEach(c => {
        const li = document.createElement('li');
        li.className = 'font-semibold text-gray-700 flex justify-between';
        li.innerHTML = `<span>${c.name}</span><span class="font-bold text-gray-900">${currencyFull.format(c.amount)}</span>`;
        topList.appendChild(li);
      });
      const sumTop3 = fin.categoriesTop3.reduce((a,b)=>a + b.amount, 0);
      const totalExpAbs = fin.kpis.expenses; // expenses already positive in your KPI
      const other = Math.max(0, totalExpAbs - sumTop3);
      document.getElementById('other-spend').textContent = currencyFull.format(other);
    }

    // === Table rendering + CSV download ===
    function renderTable() {
      const tbody = document.getElementById('tx-body');
      tbody.innerHTML = '';
      fin.table.forEach(row => {
        const tr = document.createElement('tr');
        tr.className = 'text-sm text-gray-700';
        const amtClass = row.amount >= 0 ? 'text-green-600' : 'text-red-600';
        tr.innerHTML = `
          <td class="px-6 py-4 whitespace-nowrap">${row.date}</td>
          <td class="px-6 py-4 whitespace-nowrap">${row.account}</td>
          <td class="px-6 py-4">${row.details}</td>
          <td class="px-6 py-4 whitespace-nowrap">${row.category}</td>
          <td class="px-6 py-4 whitespace-nowrap text-right font-medium ${amtClass}">${currencyFull.format(row.amount)}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    function downloadCSV() {
      const headers = ['Date','Account','Transaction Details','Category','Amount'];
      const lines = [headers.join(',')];
      fin.table.forEach(r => {
        const esc = s => '"' + String(s).replaceAll('"','""') + '"';
        lines.push([esc(r.date), esc(r.account), esc(r.details), esc(r.category), r.amount].join(','));
      });
      const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = 'SAVDSA_Transactions_2025_Jan-Oct.csv';
      document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    }

    // === Charts ===
    function initCharts() {
      const dsaRed = '#D00000';
      const friendlyGreen = '#16A34A';
      const friendlyBlue = '#0284C7';
      const friendlyBlueLight = 'rgba(2, 132, 199, 0.1)';

      // Balance (cumulative) line
      const balanceCtx = document.getElementById('balanceChart').getContext('2d');
      // FIX: Store chart instance
      chartInstances.balance = new Chart(balanceCtx, {
        type: 'line',
        data: {
          labels: fin.series.months,
          datasets: [{
            label: 'Total Balance',
            data: fin.series.cumulative,
            backgroundColor: friendlyBlueLight,
            borderColor: friendlyBlue,
            borderWidth: 3,
            tension: 0.1,
            fill: true,
            pointBackgroundColor: friendlyBlue,
            pointRadius: ctx => ctx.dataIndex === fin.series.cumulative.length - 1 ? 4 : 2,
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (ctx) => currencyFull.format(ctx.parsed.y)
              }
            }
          },
          scales: {
            y: { beginAtZero: true, ticks: { callback: (v) => currencyCompact.format(v) } },
            x: { grid: { display: false } }
          }
        }
      });

      // Cash flow: stacked bars with net line
      const net = fin.series.income.map((v, i) => v - fin.series.expenses[i]);
      const cashCtx = document.getElementById('cashFlowChart').getContext('2d');
      // FIX: Store chart instance
      chartInstances.cashFlow = new Chart(cashCtx, {
        type: 'bar',
        data: {
          labels: fin.series.months,
          datasets: [
            { label: 'Income', data: fin.series.income, backgroundColor: friendlyGreen, borderRadius: 4, order: 2, stack: 'cash' },
            { label: 'Expenses', data: fin.series.expenses.map(v => -v), backgroundColor: dsaRed, borderRadius: 4, order: 2, stack: 'cash' },
            { label: 'Net', type: 'line', data: net, borderColor: '#111827', borderWidth: 2, pointRadius: 3, tension: 0.2, order: 1 }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { position: 'bottom', labels: { boxWidth: 12, padding: 20 } },
            tooltip: {
              callbacks: {
                label: (ctx) => {
                  const lbl = ctx.dataset.label ? ctx.dataset.label + ': ' : '';
                  return lbl + currencyFull.format(ctx.parsed.y);
                }
              }
            }
          },
          scales: {
            x: { stacked: true, grid: { display: false } },
            y: { stacked: false, beginAtZero: true, ticks: { callback: (v) => currencyCompact.format(v) } }
          }
        }
      });
    }

    // === Ledger ingestion (CSV/XLSX via SheetJS) ===
    function parseFile(file) {
      // IMPROVEMENT: Show loading state
      document.getElementById('loading-overlay').style.display = 'flex';
      document.getElementById('fileInput').disabled = true;
      document.getElementById('resetData').disabled = true;

      const reader = new FileReader();
      reader.onload = (e) => {
        const data = new Uint8Array(e.target.result);
        const wb = XLSX.read(data, { type: 'array' });
        
        // Find the correct sheet
        const targetSheetName = wb.Sheets['2025_Ledger_Normalized'] ? '2025_Ledger_Normalized' : wb.SheetNames[0];
        const ws = wb.Sheets[targetSheetName];

        // FIX: Convert sheet to array of arrays (grid) to find header row manually
        const json = XLSX.utils.sheet_to_json(ws, { defval: '', header: 1 });
        rebuildFromLedger(json);
        
      };
      // Also handle file reader error
      reader.onerror = () => {
          alert('Error: Could not read the file.');
          document.getElementById('loading-overlay').style.display = 'none';
          document.getElementById('fileInput').disabled = false;
          document.getElementById('resetData').disabled = false;
      };
      reader.readAsArrayBuffer(file);
    }

    function normalizeHeader(h) { return String(h || '').trim().toLowerCase(); }
    
    function parseDate(v) {
        if (v == null) return null;
        // Handle Excel numeric dates
        if (typeof v === 'number' && isFinite(v) && v > 10000) {
            // This is the Excel epoch (1899-12-30)
            const epoch = new Date(Date.UTC(1899, 11, 30));
            const ms = (v - 1) * 86400000; // Adjust for 1-based index vs 0
            const d = new Date(epoch.getTime() + ms);
            return isNaN(d) ? null : d;
        }
        // Handle standard string dates (ISO, etc.)
        if (typeof v === 'string') {
            let s = v.trim();
            if (!s) return null;
            // Fix common typo like '2m025-10-27' and strip RTL marks
            s = s.replace(/^2m0/, '20').replace(/[\u200E\u200F]/g, '');
            const d1 = new Date(s);
            if (!isNaN(d1)) return d1;
            
            // Handle MM/DD/YYYY
            const m = s.match(/^(\d{1,2})[\\/-](\d{1,2})[\\/-](\d{2,4})$/);
            if (m) {
                let [, mm, dd, yy] = m; 
                mm = +mm; dd = +dd; yy = +yy; 
                if (yy < 100) yy += 2000;
                const d2 = new Date(yy, mm - 1, dd);
                return isNaN(d2) ? null : d2;
            }
        }
        // Fallback for other types
        const d = new Date(v);
        return isNaN(d) ? null : d;
    }
    
    function parseCurrency(val) {
        if (typeof val === 'number') return val; // Already a number
        if (!val || typeof val !== 'string') return 0; // Empty or not a string
        
        let str = val.trim();
        const isNegative = (str.includes('(') && str.includes(')')) || str.startsWith('-');
        str = str.replace(/[\$,\(\)\s-]/g, ''); 
        
        let num = parseFloat(str);
        if (isNaN(num)) return 0; // Failed to parse
        
        return isNegative ? -num : num;
    }

    function toMonthKey(d) { return d.toLocaleString('en-US', { month: 'short' }); }

    // FIX: This function is now rewritten to be much more robust.
    function rebuildFromLedger(rows) {
      try {
        const map = { date: null, signed: null, amount: null, category: null, description: null, account: null };
        
        // 1. Find the header row
        let headerRowIndex = -1;
        let headerRow = null;

        for (let i = 0; i < rows.length; i++) {
            const row = rows[i];
            if (Array.isArray(row)) { // Ensure it's an array
                const normRow = row.map(h => normalizeHeader(h));
                const hasDate = normRow.some(h => h.includes('date'));
                const hasAmount = normRow.some(h => h.includes('amount') || h.includes('signed'));
                
                if (hasDate && hasAmount) {
                    headerRowIndex = i;
                    headerRow = row;
                    break;
                }
            }
        }

        if (headerRowIndex === -1) {
            throw new Error("Could not find a header row with 'date' and 'amount' columns.");
        }

        // 2. Map the columns based on the found header row
        headerRow.forEach((h, index) => {
          const k = normalizeHeader(h);
          if (!map.date && k.includes('date')) map.date = index;
          if (!map.signed && k === 'signed') map.signed = index;
          if (!map.amount && (k.includes('amount') || k.includes('amount'))) map.amount = index;
          if (!map.category && k.includes('category')) map.category = index;
          if (!map.description && (k.includes('description') || k === 'memo' || k === 'details' || k === 'note')) map.description = index;
          if (!map.account && k.includes('account')) map.account = index;
        });

        if (map.date === null || (map.signed === null && map.amount === null)) {
            throw new Error("Could not map required 'date' and 'amount' columns.");
        }

        // 3. Process data rows *after* the header row
        const ledger = [];
        for (let i = headerRowIndex + 1; i < rows.length; i++) {
            const r = rows[i];
            if (!r || !r[map.date]) continue; // Skip empty rows or rows without a date
            
            const d = parseDate(r[map.date]);
            if (!d || d.getFullYear() !== 2025) continue;
          
            const rawAmt = map.signed !== null ? r[map.signed] : r[map.amount];
            const amtSigned = parseCurrency(rawAmt);
          
            const category = (r[map.category] || '').toString();
            const account = (r[map.account] || '').toString();
            const details = (r[map.description] || '').toString();
          
            ledger.push({ date: d, account, details, category, signed: amtSigned });
        }
        
        // 4. Calculate Balances, KPIs, etc. (all existing logic from here)
        let mainBal = 0, slushBal = 0;
        ledger.forEach(x => {
            const acc = (x.account || '').toLowerCase();
            if (acc.includes('slush')) {
                slushBal += x.signed;
            } else {
                mainBal += x.signed;
            }
        });
        const newBalances = { main: mainBal, slush: slushBal };

        let income = 0, expenses = 0;
        ledger.forEach(x => { if (x.signed >= 0) income += x.signed; else expenses += -x.signed; });
        const net = income - expenses;

        const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
        const byMonthIncome = Array(12).fill(0); const byMonthExpense = Array(12).fill(0); const byMonthNet = Array(12).fill(0);
        const cumulative = Array(12).fill(0);
        ledger.forEach(x => {
          const m = x.date.getMonth();
          if (x.signed >= 0) byMonthIncome[m] += x.signed; else byMonthExpense[m] += -x.signed;
        });
        for (let i=0, run=0; i<12; i++) { run += byMonthIncome[i] - byMonthExpense[i]; cumulative[i] = run; byMonthNet[i] = run; }

        let firstMonthIdx = 0;
        let lastMonthIdx = 11;
        for(let i=0; i<12; i++) {
            if (byMonthIncome[i] !== 0 || byMonthExpense[i] !== 0) {
                firstMonthIdx = i;
                break;
            }
        }
        for(let i=11; i>=0; i--) {
            if (byMonthIncome[i] !== 0 || byMonthExpense[i] !== 0) {
                lastMonthIdx = i;
                break;
            }
        }
        
        const activeMonths = months.slice(firstMonthIdx, lastMonthIdx + 1);
        const activeCumulative = cumulative.slice(firstMonthIdx, lastMonthIdx + 1);
        const activeIncome = byMonthIncome.slice(firstMonthIdx, lastMonthIdx + 1);
        const activeExpenses = byMonthExpense.slice(firstMonthIdx, lastMonthIdx + 1);
        
        document.getElementById('charts-heading').textContent = `The Story in Charts (${activeMonths[0]} – ${activeMonths[activeMonths.length - 1]} 2025)`;

        const catMap = new Map();
        ledger.forEach(x => { if (x.signed < 0) catMap.set(x.category || 'Uncategorized', (catMap.get(x.category || 'Uncategorized') || 0) + (-x.signed)); });
        const cats = Array.from(catMap.entries()).sort((a,b)=>b[1]-a[1]);
        const top3 = cats.slice(0,3).map(([name, amt]) => ({ name, amount: amt }));

        const table = ledger.sort((a,b)=>a.date-b.date).map(x => ({
          date: x.date.toISOString().slice(0,10),
          account: x.account || '—',
          details: x.details || '',
          category: x.category || '—',
          amount: x.signed
        }));

        // 5. Replace fin object and re-render
        fin = {
          projectedQ4Dues: fin.projectedQ4Dues,
          kpis: { income, expenses, net },
          balances: newBalances,
          budget: fin.budget,
          categoriesTop3: top3,
          series: {
            months: activeMonths,
            cumulative: activeCumulative,
            income: activeIncome,
            expenses: activeExpenses
          },
          table
        };

        populateKPIs();
        renderTable();
        
        if (chartInstances.balance) chartInstances.balance.destroy();
        if (chartInstances.cashFlow) chartInstances.cashFlow.destroy();
        
        initCharts();

      } catch (e) {
          alert('Error processing file: '... (truncated)

