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
    // Expecting an array of objects: [{ medicine, frequency, days }]
    if (!Array.isArray(json)) return (viewEl.innerHTML = ''), hide(viewEl);
    if (json.length === 0) return (viewEl.innerHTML = '<p>No medicines found.</p>'), unhide(viewEl);
    const rows = json.map((item) => {
      const med = item.medicine ?? '-';
      const freq = item.frequency ?? '-';
      const days = item.days ?? '-';
      return `<tr><td>${med}</td><td>${freq}</td><td>${days}</td></tr>`;
    }).join('');
    viewEl.innerHTML = `
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

    const days = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"];
    const dayCards = days.filter(d => plan[d]).map(day => {
      const d = plan[day] || {};
      return `
        <div class="day-card">
          <div class="day-name">${day[0].toUpperCase()+day.slice(1)}</div>
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
        renderHealthRisk(viewHealthRisk, data);

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
    item.textContent = text;
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
})();


