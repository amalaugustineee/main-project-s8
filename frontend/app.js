(() => {
  const $ = (sel) => document.querySelector(sel);
  const apiBaseInput = $('#apiBase');
  const saveBaseBtn = $('#saveBase');

  const getBase = () => {
    const saved = localStorage.getItem('apiBase');
    if (saved) return saved;
    return apiBaseInput && apiBaseInput.value ? apiBaseInput.value.trim() : 'http://127.0.0.1:8000';
  };
  const setBase = (v) => localStorage.setItem('apiBase', v);

  // Initialize base URL from localStorage
  const saved = localStorage.getItem('apiBase');
  if (saved && apiBaseInput) apiBaseInput.value = saved;

  let currentHealthRiskData = null; // Store last analysis for saving


  if (saveBaseBtn && apiBaseInput) {
    saveBaseBtn.addEventListener('click', () => {
      setBase(apiBaseInput.value.trim());
      alert('Saved API base URL');
    });
  }

  async function postFormData(url, formData) {
    const res = await fetch(url, { method: 'POST', body: formData });
    const contentType = res.headers.get('content-type') || '';
    if (!res.ok) {
      // Try to extract error JSON from FastAPI
      if (contentType.includes('application/json')) {
        const err = await res.json();
        throw new Error(err.detail || JSON.stringify(err));
      }
      throw new Error(`HTTP ${res.status}`);
    }
    if (contentType.includes('application/json')) return res.json();
    // Fallback to text
    return res.text();
  }

  function showJSON(targetEl, data) {
    targetEl.textContent = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
  }

  function unhide(el) { el.classList.remove('hidden'); }
  function hide(el) { el.classList.add('hidden'); }

  // Renderers
  function renderPrescription(viewEl, json) {
    // Expecting object: { doctor_name, hospital_name, medicines: [] }
    // Or legacy array support just in case
    let meds = [];
    let meta = "";

    if (Array.isArray(json)) {
      meds = json;
    } else if (json && typeof json === 'object') {
      meds = Array.isArray(json.medicines) ? json.medicines : [];
      if (json.doctor_name || json.hospital_name) {
        meta = `<div class="panel">
                   <div class="kv"><span>Doctor</span><span>${json.doctor_name || 'Unknown'}</span></div>
                   <div class="kv"><span>Hospital</span><span>${json.hospital_name || 'Unknown'}</span></div>
                 </div>`;
      }
    } else {
      return (viewEl.innerHTML = ''), hide(viewEl);
    }

    if (meds.length === 0) return (viewEl.innerHTML = meta + '<p>No medicines found.</p>'), unhide(viewEl);

    const rows = meds.map((item) => {
      const med = item.medicine ?? '-';
      const freq = item.frequency ?? '-';
      const days = item.days ?? '-';
      return `<tr><td>${med}</td><td>${freq}</td><td>${days}</td></tr>`;
    }).join('');

    viewEl.innerHTML = meta + `
      <table class="table">
        <thead><tr><th>Medicine</th><th>Frequency</th><th>Days</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    `;
    unhide(viewEl);
  }

  function renderHealthRisk(viewEl, json) {
    // Expecting { summary, tests: [{ name, current_value, safe_range, risk_percent, risk_reason, pubmed_support?[] }] }
    if (!json || typeof json !== 'object') return (viewEl.innerHTML = ''), hide(viewEl);
    const summary = json.summary ? `<p class="summary">${json.summary}</p>` : '';
    const tests = Array.isArray(json.tests) ? json.tests : [];
    const cards = tests.map((t) => {
      const pubs = Array.isArray(t.pubmed_support) ? t.pubmed_support : [];
      const links = pubs.map(p => `<li><a href="${p.url}" target="_blank" rel="noopener">${p.title || p.source || 'PubMed link'}</a> <small>${p.pubdate || ''}</small></li>`).join('');
      return `
        <div class="risk-card">
          <div class="risk-head">
            <div class="risk-name">${t.name || '-'}</div>
            <div class="risk-percent">${t.risk_percent ?? '-'}%</div>
          </div>
          <div class="risk-meta">
            <div><strong>Current:</strong> ${t.current_value || '-'}</div>
            <div><strong>Range:</strong> ${t.safe_range || '-'}</div>
          </div>
          <div class="risk-reason">${t.risk_reason || ''}</div>
          ${links ? `<ul class="pubmed">${links}</ul>` : ''}
        </div>`;
    }).join('');
    viewEl.innerHTML = `${summary}<div class="risk-grid">${cards}</div>`;
    unhide(viewEl);
  }

  function renderDiet(viewEl, json) {
    // Expecting shape from schema: { patient_info, lab_analysis, diet_plan, recommendations }
    if (!json || typeof json !== 'object') return (viewEl.innerHTML = ''), hide(viewEl);
    const pi = json.patient_info || {};
    const lab = json.lab_analysis || {};
    const plan = json.diet_plan || {};
    const rec = json.recommendations || {};

    const patient = `
      <div class="panel">
        <h3>Patient</h3>
        <div class="kv"><span>Region</span><span>${pi.region || '-'}</span></div>
        <div class="kv"><span>Condition</span><span>${pi.condition || '-'}</span></div>
        <div class="kv"><span>Weight</span><span>${pi.weight_kg || '-'}</span></div>
        <div class="kv"><span>Age</span><span>${pi.age || '-'}</span></div>
      </div>`;

    const labRows = Array.isArray(lab.extracted_values) ? lab.extracted_values.map(ev =>
      `<tr><td>${ev.parameter || '-'}</td><td>${ev.value ?? '-'}</td><td>${ev.unit || '-'}</td><td>${ev.status || '-'}</td></tr>`
    ).join('') : '';
    const labBlock = `
      <div class="panel">
        <h3>Lab Analysis</h3>
        ${lab.summary ? `<p class="summary">${lab.summary}</p>` : ''}
        ${labRows ? `<table class="table"><thead><tr><th>Parameter</th><th>Value</th><th>Unit</th><th>Status</th></tr></thead><tbody>${labRows}</tbody></table>` : '<p>No extracted values.</p>'}
      </div>`;

    const days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
    const dayCards = days.filter(d => plan[d]).map(day => {
      const d = plan[day] || {};
      return `
        <div class="day-card">
          <div class="day-name">${day[0].toUpperCase() + day.slice(1)}</div>
          <div class="meal"><strong>Breakfast:</strong> ${d.breakfast || '-'}</div>
          <div class="meal"><strong>Lunch:</strong> ${d.lunch || '-'}</div>
          <div class="meal"><strong>Dinner:</strong> ${d.dinner || '-'}</div>
          <div class="meal"><strong>Snacks:</strong> ${d.snacks || '-'}</div>
        </div>`;
    }).join('');
    const planBlock = `
      <div class="panel">
        <h3>7-Day Diet Plan</h3>
        <div class="days-grid">${dayCards || '<p>No plan available.</p>'}</div>
      </div>`;

    const list = (arr) => Array.isArray(arr) && arr.length ? `<ul>${arr.map(x => `<li>${x}</li>`).join('')}</ul>` : '<p>-</p>';
    const recBlock = `
      <div class="panel">
        <h3>Recommendations</h3>
        <div class="cols">
          <div>
            <h4>Include</h4>
            ${list(rec.foods_to_include)}
          </div>
          <div>
            <h4>Avoid</h4>
            ${list(rec.foods_to_avoid)}
          </div>
          <div>
            <h4>Key Nutrients</h4>
            ${list(rec.key_nutrients)}
          </div>
        </div>
        ${rec.hydration ? `<p><strong>Hydration:</strong> ${rec.hydration}</p>` : ''}
        ${rec.exercise ? `<p><strong>Exercise:</strong> ${rec.exercise}</p>` : ''}
      </div>`;

    viewEl.innerHTML = `<div class="diet-grid">${patient}${labBlock}${planBlock}${recBlock}</div>`;
    unhide(viewEl);
  }

  // 1) Prescription
  const formPrescription = $('#formPrescription');
  const outPrescription = $('#outPrescription');
  const viewPrescription = $('#viewPrescription');
  if (formPrescription && outPrescription && viewPrescription) {
    formPrescription.addEventListener('submit', async (e) => {
      e.preventDefault();
      outPrescription.textContent = 'Uploading...';
      const fd = new FormData(formPrescription);
      try {
        const base = getBase();
        const data = await postFormData(`${base}/prescription`, fd);
        showJSON(outPrescription, data);
        renderPrescription(viewPrescription, data);
      } catch (err) {
        outPrescription.textContent = `Error: ${err.message}`;
        hide(viewPrescription);
      }
    });
  }

  // 2) Health Risk
  const formHealthRisk = $('#formHealthRisk');
  const outHealthRisk = $('#outHealthRisk');
  const viewHealthRisk = $('#viewHealthRisk');
  let riskChartInstance = null;
  if (formHealthRisk && outHealthRisk && viewHealthRisk) {
    formHealthRisk.addEventListener('submit', async (e) => {
      e.preventDefault();
      outHealthRisk.textContent = 'Uploading...';
      const fd = new FormData(formHealthRisk);
      try {
        const base = getBase();
        const data = await postFormData(`${base}/healthrisk`, fd);
        showJSON(outHealthRisk, data);
        currentHealthRiskData = data; // Store for saving
        renderHealthRisk(viewHealthRisk, data);

        // Show save button
        const btnSave = $('#btnSaveReport');
        if (btnSave) unhide(btnSave);

        // Dashboard chart: risk_percent per test
        const tests = Array.isArray(data.tests) ? data.tests : [];
        const labels = tests.map(t => t.name || '-');
        const values = tests.map(t => Number.isFinite(t.risk_percent) ? t.risk_percent : 0);
        const ctx = document.getElementById('riskChart');
        if (ctx && 'Chart' in window) {
          if (riskChartInstance) {
            riskChartInstance.destroy();
          }
          riskChartInstance = new Chart(ctx, {
            type: 'bar',
            data: {
              labels,
              datasets: [{
                label: 'Risk %',
                data: values,
                backgroundColor: values.map(v => v >= 70 ? 'rgba(255,99,132,0.7)' : v >= 40 ? 'rgba(255,206,86,0.7)' : 'rgba(75,192,192,0.7)'),
                borderColor: 'rgba(255,255,255,0.2)',
                borderWidth: 1
              }]
            },
            options: {
              responsive: true,
              plugins: {
                legend: { display: false },
                tooltip: { callbacks: { label: (ctx) => `${ctx.parsed.y}%` } }
              },
              scales: {
                y: { beginAtZero: true, max: 100, grid: { color: 'rgba(255,255,255,0.08)' } },
                x: { grid: { color: 'rgba(255,255,255,0.04)' } }
              }
            }
          });
        }
      } catch (err) {
        outHealthRisk.textContent = `Error: ${err.message}`;
        hide(viewHealthRisk);
        if (riskChartInstance) { riskChartInstance.destroy(); riskChartInstance = null; }
      }
    });
  }

  // 2b) Save Report Handler
  const btnSaveReport = $('#btnSaveReport');
  if (btnSaveReport) {
    btnSaveReport.addEventListener('click', async () => {
      if (!currentHealthRiskData) return alert('No report to save!');
      btnSaveReport.textContent = 'Saving...';
      btnSaveReport.disabled = true;
      try {
        const base = getBase();
        const res = await fetch(`${base}/reports/save`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ analysis_result: currentHealthRiskData })
        });
        const respData = await res.json();
        if (!res.ok) throw new Error(respData.detail || 'Save failed');
        alert('Report saved successfully!');
        btnSaveReport.textContent = 'Saved';
      } catch (err) {
        alert(`Error saving report: ${err.message}`);
        btnSaveReport.textContent = 'Save Report to History';
        btnSaveReport.disabled = false;
      }
    });
  }

  // 2c) Trends Page Logic
  const trendParamSelect = $('#trendParam');
  const btnLoadTrend = $('#btnLoadTrend');
  const trendStatus = $('#trendStatus');
  let trendChartInstance = null;

  async function loadTrendParameters() {
    try {
      const base = getBase();
      const res = await fetch(`${base}/trends`);
      if (!res.ok) throw new Error('Failed to load parameters');
      const data = await res.json();
      const params = data.parameters || [];
      trendParamSelect.innerHTML = '<option value="">-- Select a Test --</option>' +
        params.map(p => `<option value="${p}">${p}</option>`).join('');
    } catch (e) {
      console.error(e);
      if (trendStatus) trendStatus.textContent = "Could not load test parameters.";
    }
  }

  async function loadTrendData(testName) {
    if (!testName) return;
    if (trendStatus) trendStatus.textContent = 'Loading...';
    try {
      const base = getBase();
      const res = await fetch(`${base}/trends/${encodeURIComponent(testName)}`);
      if (!res.ok) throw new Error('Failed to load data');
      const data = await res.json();
      if (trendStatus) trendStatus.textContent = '';
      renderTrendChart(testName, data);
    } catch (e) {
      if (trendStatus) trendStatus.textContent = `Error: ${e.message}`;
    }
  }

  function renderTrendChart(label, data) {
    // data: [{timestamp, value, unit, risk_percent, ...}]
    const ctx = document.getElementById('trendChart');
    if (!ctx) return;

    const points = data.map(d => ({ x: d.timestamp, y: d.value }));
    const riskPoints = data.map(d => ({ x: d.timestamp, y: d.risk_percent }));

    if (trendChartInstance) trendChartInstance.destroy();

    trendChartInstance = new Chart(ctx, {
      type: 'line',
      data: {
        datasets: [
          {
            label: `${label} Value`,
            data: points,
            borderColor: 'blue',
            yAxisID: 'y'
          },
          {
            label: 'Risk %',
            data: riskPoints,
            borderColor: 'red',
            borderDash: [5, 5],
            yAxisID: 'y1'
          }
        ]
      },
      options: {
        responsive: true,
        scales: {
          x: {
            type: 'time',
            time: { unit: 'day' }
          },
          y: {
            type: 'linear',
            display: true,
            position: 'left',
            title: { display: true, text: 'Value' }
          },
          y1: {
            type: 'linear',
            display: true,
            position: 'right',
            title: { display: true, text: 'Risk %' },
            min: 0, max: 100,
            grid: { drawOnChartArea: false }
          }
        }
      }
    });
  }

  if (trendParamSelect) {
    loadTrendParameters();
    if (btnLoadTrend) {
      btnLoadTrend.addEventListener('click', () => loadTrendData(trendParamSelect.value));
    }
    trendParamSelect.addEventListener('change', () => loadTrendData(trendParamSelect.value));
  }

  // 3) Diet Plan
  const formDiet = $('#formDiet');
  const outDiet = $('#outDiet');
  const viewDiet = $('#viewDiet');
  if (formDiet && outDiet && viewDiet) {
    formDiet.addEventListener('submit', async (e) => {
      e.preventDefault();
      outDiet.textContent = 'Uploading...';
      const fd = new FormData(formDiet);
      try {
        const base = getBase();
        const data = await postFormData(`${base}/generate-diet-plan`, fd);
        showJSON(outDiet, data);
        renderDiet(viewDiet, data);
      } catch (err) {
        outDiet.textContent = `Error: ${err.message}`;
        hide(viewDiet);
      }
    });
  }

  // 4) Wellbeing Chat on Home page
  const chatForm = document.getElementById('chatForm');
  const chatInput = document.getElementById('chatInput');
  const chatMessages = document.getElementById('chatMessages');
  function appendMsg(role, text) {
    const item = document.createElement('div');
    item.className = `chat-msg ${role}`;
    if (window.markdownit) {
      item.innerHTML = window.markdownit().render(text);
    } else {
      item.textContent = text;
    }
    chatMessages.appendChild(item);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }
  if (chatForm && chatInput && chatMessages) {
    chatForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const q = chatInput.value.trim();
      if (!q) return;
      appendMsg('user', q);
      chatInput.value = '';
      appendMsg('assistant pending', 'Thinking...');
      try {
        const base = getBase();
        const res = await fetch(`${base}/wellbeing-chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: q })
        });
        const data = await res.json();
        chatMessages.lastChild.remove();
        if (!res.ok) throw new Error(data.detail || 'Request failed');
        appendMsg('assistant', data.answer || '');
      } catch (err) {
        chatMessages.lastChild.remove();
        appendMsg('assistant', `Error: ${err.message}`);
      }
    });
  }
  // 5) Health Summary
  const btnLoadSummary = $('#btnLoadSummary');
  const viewSummary = $('#viewSummary');
  const summaryContent = $('#summaryContent');

  if (btnLoadSummary && viewSummary && summaryContent) {
    // New Feature: Load History on Page Load
    const historyReports = $('#historyReports');
    const historyPrescriptions = $('#historyPrescriptions');

    async function loadHistory() {
      if (!historyReports || !historyPrescriptions) return [];
      let labsData = []; // Store to return

      try {
        const base = getBase();

        // 1. Fetch Lab Reports
        try {
          const resLab = await fetch(`${base}/reports/history`);
          if (resLab.ok) {
            const labs = await resLab.json();
            labsData = labs; // Save for chart
            if (Array.isArray(labs) && labs.length) {
              historyReports.innerHTML = `<ul class="hist-list">${labs.map(r =>
                `<li><strong>${r.created_at ? r.created_at.slice(0, 10) : 'Date N/A'}</strong>: ${r.summary || 'No summary'}</li>`
              ).join('')}</ul>`;
            } else {
              historyReports.innerHTML = '<p>No lab reports found.</p>';
            }
          } else {
            historyReports.innerHTML = '<p class="error">Failed to load reports.</p>';
          }
        } catch (e) { console.error('Lab fetch error', e); }

        // 2. Fetch Prescriptions
        try {
          const resPres = await fetch(`${base}/prescription/history`);
          if (resPres.ok) {
            const pres = await resPres.json();
            if (Array.isArray(pres) && pres.length) {
              historyPrescriptions.innerHTML = `<ul class="hist-list">${pres.map(p =>
                `<li><strong>${p.created_at ? p.created_at.slice(0, 10) : 'Date N/A'}</strong>: ${p.doctor_name || 'MD'} - ${p.medicines ? p.medicines.length + ' meds' : ''}</li>`
              ).join('')}</ul>`;
            } else {
              historyPrescriptions.innerHTML = '<p>No prescriptions found.</p>';
            }
          } else {
            historyPrescriptions.innerHTML = '<p class="error">Failed to load prescriptions.</p>';
          }
        } catch (e) { console.error('Presc fetch error', e); }

        return labsData;

      } catch (e) {
        console.error(e);
        if (historyReports) historyReports.innerText = 'Error loading history.';
        if (historyPrescriptions) historyPrescriptions.innerText = 'Error loading history.';
        return [];
      }
    }

    // Call on load
    console.log('Calling loadHistory...');
    loadHistory().then(labs => {
      console.log('loadHistory finished');
      // Render Chart if we have lab data
      if (Array.isArray(labs) && labs.length > 0) {
        renderSummaryChart(labs);
      }
    }).catch(e => console.error(e));

    function renderSummaryChart(labs) {
      const ctx = document.getElementById('summaryChart');
      const container = document.getElementById('summaryGraphs');
      if (!ctx) return;

      // Extract all test results from all reports
      // labs is list of HealthReport: [{ created_at, test_results: [...] }, ...]
      // We want to map: TestName -> [{x: time, y: value}]

      const datasets = {};

      // Sort labs by date (should be already sorted desc by backend, but for graph we need asc)
      const sortedLabs = [...labs].sort((a, b) => new Date(a.created_at) - new Date(b.created_at));

      sortedLabs.forEach(report => {
        if (!report.test_results) return;
        const date = report.created_at;

        report.test_results.forEach(tr => {
          const name = tr.test_name;
          // Filter mostly numeric tests or specific important ones
          if (!datasets[name]) {
            datasets[name] = [];
          }
          datasets[name].push({ x: date, y: tr.risk_percent });
        });
      });

      // Select top 3-5 interesting datasets or ALL?
      // Let's pick 5 with most data points
      const keys = Object.keys(datasets).sort((a, b) => datasets[b].length - datasets[a].length).slice(0, 5);

      if (keys.length === 0) return; // No data
      if (container) unhide(container);

      // Define colors
      const colors = ['#2563eb', '#dc2626', '#16a34a', '#d97706', '#9333ea'];

      const chartData = keys.map((key, i) => ({
        label: key,
        data: datasets[key],
        borderColor: colors[i % colors.length],
        backgroundColor: colors[i % colors.length],
        tension: 0.3,
        fill: false
      }));

      // Destroy old instance? Access global or attach to canvas
      if (ctx.chart) ctx.chart.destroy();

      ctx.chart = new Chart(ctx, {
        type: 'line',
        data: {
          datasets: chartData
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: 'index', intersect: false },
          plugins: {
            title: { display: true, text: 'Health Risk Trends (%)' },
            tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y}% Risk` } }
          },
          scales: {
            x: { type: 'time', time: { unit: 'day' } },
            y: {
              beginAtZero: true,
              max: 100,
              title: { display: true, text: 'Risk Percentage (%)' }
            }
          }
        }
      });
    }

    btnLoadSummary.addEventListener('click', async () => {
      btnLoadSummary.disabled = true;
      btnLoadSummary.textContent = 'Generating Analysis...';
      try {
        const base = getBase();
        const res = await fetch(`${base}/health/summary`, {
          method: 'POST'
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Failed to generate summary');

        // Render MD
        const md = window.markdownit ? window.markdownit() : null;
        if (md) {
          summaryContent.innerHTML = md.render(data.analysis || 'No analysis returned.');
        } else {
          summaryContent.textContent = data.analysis;
          summaryContent.style.whiteSpace = 'pre-wrap';
        }
        unhide(viewSummary);
      } catch (err) {
        summaryContent.innerHTML = `<p class="error" style="color:red">Error: ${err.message}</p>`;
        unhide(viewSummary);
      } finally {
        btnLoadSummary.disabled = false;
        btnLoadSummary.textContent = 'Generate Summary';
      }
    });
  }
})();

// ---------- 5. Notifications (WebSocket) ----------
function setupNotifications() {
  // Use current host or default for dev
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const host = window.location.host || '127.0.0.1:8000';
  // If running via file://, force localhost
  const wsHost = window.location.protocol === 'file:' ? '127.0.0.1:8000' : host;
  const wsUrl = `ws://${wsHost}/ws/notifications`;

  console.log("Connecting to WebSocket:", wsUrl);
  const socket = new WebSocket(wsUrl);

  socket.onopen = () => {
    console.log("✅ WebSocket Connected");
  };

  socket.onmessage = (event) => {
    console.log("🔔 Notification:", event.data);
    showToast(event.data);
  };

  socket.onclose = () => {
    console.log("⚠️ WebSocket Disconnected. Retrying in 5s...");
    setTimeout(setupNotifications, 5000);
  };

  socket.onerror = (err) => {
    // console.error("WebSocket Error:", err);
    socket.close();
  };
}

function showToast(message) {
  // Create toast element
  const toast = document.createElement('div');
  toast.className = 'toast-notification';
  toast.innerHTML = `
    <div style="display:flex; align-items:center; gap:10px;">
      <span style="font-size:1.5rem;">💊</span>
      <div>${window.markdownit ? window.markdownit().render(message) : message}</div>
    </div>
  `;

  // Style it (or move to CSS)
  Object.assign(toast.style, {
    position: 'fixed',
    top: '20px',
    right: '20px',
    background: 'white',
    color: '#333',
    padding: '15px 20px',
    borderRadius: '12px',
    boxShadow: '0 4px 15px rgba(0,0,0,0.2)',
    zIndex: '9999',
    minWidth: '300px',
    borderLeft: '5px solid #2563eb',
    animation: 'slideIn 0.5s ease-out'
  });

  document.body.appendChild(toast);

  // Remove after 10 seconds
  setTimeout(() => {
    toast.style.animation = 'fadeOut 0.5s ease-in';
    setTimeout(() => toast.remove(), 450);
  }, 10000); // 10s display
}

// Add simple CSS animation for toast
const style = document.createElement('style');
style.innerHTML = `
  @keyframes slideIn { from { transform: translateX(100%); opacity: 0; } to { transform: translateX(0); opacity: 1; } }
  @keyframes fadeOut { from { opacity: 1; } to { opacity: 0; transform: translateY(-20px); } }
`;
document.head.appendChild(style);

// Start on load
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', setupNotifications);
} else {
  // setupNotifications();
}


// 6. Medicine Queue Logic
async function loadReminders(targetEl) {
  // Use passed element or find it
  const reminderQueue = targetEl || document.getElementById('reminderQueue');
  if (!reminderQueue) {
    console.error("reminderQueue element not found in DOM");
    return;
  }

  // Local helper to fix scope issue (getBase is inside IIFE)
  const getApiBase = () => {
    const inp = document.getElementById('apiBase');
    return localStorage.getItem('apiBase') || (inp && inp.value ? inp.value.trim() : 'http://127.0.0.1:8000');
  };

  try {
    const base = getApiBase();

    // Show loading state if empty
    if (!reminderQueue.querySelector('.med-item')) {
      reminderQueue.innerHTML = '<p style="color:gray; font-size:0.9em">Fetching upcoming medicines...</p>';
    }

    const res = await fetch(`${base}/reminders/upcoming`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (data.length === 0) {
      reminderQueue.innerHTML = '<p>No upcoming medicines found.</p>';
      return;
    }

    // Render Queue
    reminderQueue.innerHTML = data.map(item => `
      <div class="med-item" style="background: white; padding: 10px 15px; border-radius: 8px; border-left: 5px solid #2563eb; box-shadow: 0 2px 4px rgba(0,0,0,0.05); display: flex; justify-content: space-between; align-items: center;">
        <div>
          <div style="font-weight: bold; font-size: 1.1em;">${item.medicine}</div>
          <div style="font-size: 0.9em; color: #666;">${item.instruction}</div>
        </div>
        <div style="text-align: right;">
          <div style="font-weight: bold; color: #2563eb; font-size: 1.2em;">${item.time}</div>
          <div style="font-size: 0.8em; color: #888;">${item.date}</div>
        </div>
      </div>
    `).join('');

  } catch (e) {
    console.error(e);
    const base = getApiBase(); // Use local safe helper
    reminderQueue.innerHTML = `<p style="color:red; font-size:0.9em;">Error: <b>${e.message}</b><br>Target: ${base}/reminders/upcoming</p>`;
  }
}


// Load on start
document.addEventListener('DOMContentLoaded', () => {
  const qEl = document.getElementById('reminderQueue');
  // Immediate feedback
  if (qEl) qEl.innerHTML = '<p>State: 1. Init</p>';

  // Bind button
  const btn = document.getElementById('btnRefreshQueue');
  if (btn) btn.addEventListener('click', () => loadReminders(qEl));

  loadReminders(qEl);
  setInterval(() => loadReminders(qEl), 60000);
});
