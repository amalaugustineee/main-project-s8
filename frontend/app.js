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

  // ─── GLOBAL TOAST ─────────────────────────────────────────────────────────
  // A persistent floating bar that survives page navigation by checking
  // localStorage for active jobs on every page load.
  function getOrCreateToast() {
    let t = document.getElementById('_analysisToast');
    if (!t) {
      t = document.createElement('div');
      t.id = '_analysisToast';
      t.style.cssText = [
        'position:fixed', 'bottom:24px', 'right:24px', 'z-index:9999',
        'background:#2D302D', 'color:#fff', 'padding:14px 20px',
        'border-radius:16px', 'font-size:13px', 'font-weight:600',
        'box-shadow:0 8px 24px rgba(0,0,0,0.25)', 'display:none',
        'max-width:320px', 'line-height:1.5', 'cursor:pointer'
      ].join(';');
      document.body.appendChild(t);
    }
    return t;
  }

  function showToast(msg, type = 'info') {
    const t = getOrCreateToast();
    const colors = { info: '#6B9F6F', done: '#4D6B53', error: '#B85C3C', processing: '#D47B5A' };
    const icons = { info: '⏳', done: '✅', error: '❌', processing: '🔄' };
    t.style.borderLeft = `4px solid ${colors[type] || colors.info}`;
    t.innerHTML = `${icons[type] || '⏳'} ${msg}`;
    t.style.display = 'block';
  }

  function hideToast() {
    const t = document.getElementById('_analysisToast');
    if (t) t.style.display = 'none';
  }

  // ─── JOB POLLING ──────────────────────────────────────────────────────────
  // Jobs are stored in localStorage as:
  //   mediware_jobs: [ {job_id, type, ts} ]
  // so they survive page navigation.

  function saveJob(jobId, type) {
    const jobs = JSON.parse(localStorage.getItem('mediware_jobs') || '[]');
    jobs.push({ job_id: jobId, type, ts: Date.now() });
    localStorage.setItem('mediware_jobs', JSON.stringify(jobs));
  }

  function removeJob(jobId) {
    const jobs = JSON.parse(localStorage.getItem('mediware_jobs') || '[]');
    localStorage.setItem('mediware_jobs', JSON.stringify(jobs.filter(j => j.job_id !== jobId)));
  }

  function getActiveJobs() {
    return JSON.parse(localStorage.getItem('mediware_jobs') || '[]')
      .filter(j => Date.now() - j.ts < 30 * 60 * 1000); // Discard jobs older than 30 min
  }

  async function pollJob(jobId, type, onDone, onError) {
    const base = getBase();
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${base}/jobs/${jobId}`);
        const data = await res.json();
        if (data.status === 'done') {
          clearInterval(interval);
          removeJob(jobId);
          hideToast();
          onDone(data.result);
        } else if (data.status === 'failed') {
          clearInterval(interval);
          removeJob(jobId);
          showToast(`Analysis failed: ${data.error || 'Unknown error'}`, 'error');
          setTimeout(hideToast, 6000);
          if (onError) onError(data.error);
        } else {
          // Still processing
          const elapsed = Math.round((Date.now() - (parseInt(jobId.split('-')[0], 16) || Date.now())) / 1000);
          showToast(`Analyzing ${type}… this may take 30–60s. You can browse other pages.`, 'processing');
        }
      } catch (e) {
        // Network error — keep polling
        showToast(`Waiting for ${type} analysis…`, 'processing');
      }
    }, 3000);
  }

  // Resume any in-progress jobs from a previous page (localStorage persistence)
  function resumeActiveJobs() {
    const active = getActiveJobs();
    if (active.length === 0) return;
    showToast(`${active.length} analysis job(s) running in background…`, 'processing');
    for (const job of active) {
      pollJob(
        job.job_id,
        job.type,
        (result) => {
          // When done: if we're on the right page, render; otherwise just notify
          showToast(`✅ ${job.type} analysis complete! Go to the ${job.type} page to view results.`, 'done');
          // Store result in sessionStorage for the target page to pick up
          sessionStorage.setItem(`result_${job.type}_${job.job_id}`, JSON.stringify(result));
          setTimeout(hideToast, 8000);
        },
        null
      );
    }
  }

  resumeActiveJobs();
  // ─── END JOB POLLING ──────────────────────────────────────────────────────


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
    let meds = [];
    let meta = "";

    if (Array.isArray(json)) {
      meds = json;
    } else if (json && typeof json === 'object') {
      meds = Array.isArray(json.medicines) ? json.medicines : [];

      let interactionHtml = '';
      if (json.interactions && json.interactions.has_interactions && json.interactions.warnings?.length > 0) {
        const warnings = json.interactions.warnings.map(w => `<li class="text-xs text-[#991b1b] mt-1">${w}</li>`).join('');
        interactionHtml = `
          <div class="bg-[#fee2e2] border-l-4 border-[#ef4444] p-4 mt-4 rounded-r-xl">
            <p class="font-bold flex items-center gap-2 text-[#991b1b] text-sm mb-2">
              <iconify-icon icon="lucide:alert-triangle"></iconify-icon> Drug Interaction Warning
            </p>
            <ul class="list-disc pl-5">
              ${warnings}
            </ul>
          </div>
        `;
      }

      if (json.doctor_name || json.hospital_name || json.prescription_id) {
        meta = `
          <div class="bg-white p-6 rounded-3xl border border-[#F5EFE6] shadow-sm mb-6 flex flex-wrap gap-6 items-center justify-between">
            <div class="flex gap-8">
               <div><span class="text-[10px] uppercase font-bold text-[#8B7355] tracking-widest block">Doctor</span><span class="font-bold text-[#2D302D]">${json.doctor_name || 'Unknown'}</span></div>
               <div><span class="text-[10px] uppercase font-bold text-[#8B7355] tracking-widest block">Hospital</span><span class="font-bold text-[#2D302D]">${json.hospital_name || 'Unknown'}</span></div>
            </div>
            ${json.prescription_id ? `<a href="${getBase()}/prescription/${json.prescription_id}/calendar" target="_blank" class="px-4 py-2 bg-[#6B9F6F] text-white text-xs font-bold rounded-full shadow-md hover:bg-[#4D6B53] flex items-center gap-2"><iconify-icon icon="lucide:calendar"></iconify-icon> Export Calendar</a>` : ''}
          </div>
          ${interactionHtml}
        `;
      }
    } else {
      return (viewEl.innerHTML = ''), hide(viewEl);
    }

    if (meds.length === 0) return (viewEl.innerHTML = meta + '<p class="text-[#6D726D]">No medicines found.</p>'), unhide(viewEl);

    const rows = meds.map((item) => {
      const med = item.medicine ?? '-';
      const freq = item.frequency ?? '-';
      const days = item.days ?? '-';
      return `
        <div class="bg-white p-4 rounded-2xl border border-[#F5EFE6] flex justify-between items-center shadow-sm">
           <div class="flex items-center gap-4">
              <div class="w-10 h-10 bg-[#88A68B]/10 rounded-xl flex items-center justify-center text-[#88A68B]"><iconify-icon icon="lucide:pill" class="text-xl"></iconify-icon></div>
              <div>
                 <div class="font-bold text-[#2D302D]">${med}</div>
                 <div class="text-xs text-[#8B7355]">${freq}</div>
              </div>
           </div>
           <div class="px-3 py-1 bg-[#F5F1E8] text-[#8B7355] text-xs font-bold rounded-lg">${days} Days</div>
        </div>
      `;
    }).join('');

    viewEl.innerHTML = meta + `<div class="space-y-3 mt-6">${rows}</div>`;
    unhide(viewEl);
  }

  function renderHealthRisk(viewEl, json) {
    if (!json || typeof json !== 'object') return (viewEl.innerHTML = ''), hide(viewEl);
    const summary = json.summary ? `<p class="mb-6 text-sm text-[#4D6B53] font-medium leading-relaxed bg-[#6B9F6F]/10 p-4 rounded-2xl border border-[#6B9F6F]/20">${json.summary}</p>` : '';
    const tests = Array.isArray(json.tests) ? json.tests : [];

    const cards = tests.map((t) => {
      const isHighRisk = t.risk_percent >= 40;
      const colorCls = isHighRisk ? 'text-[#B85C3C] bg-[#B85C3C]/10' : 'text-[#6B9F6F] bg-[#6B9F6F]/10';
      const borderCls = isHighRisk ? 'border-[#B85C3C]/20' : 'border-[#6B9F6F]/20';

      const pubs = Array.isArray(t.pubmed_support) ? t.pubmed_support : [];
      const links = pubs.map(p => `<a href="${p.url}" target="_blank" class="block text-[10px] text-[#88A68B] hover:underline hover:text-[#4D6B53] mt-1 line-clamp-1">${p.title || p.source}</a>`).join('');

      return `
        <div class="bg-white p-6 rounded-[24px] border ${borderCls} shadow-sm flex flex-col justify-between hover:-translate-y-1 transition-transform">
          <div>
            <div class="flex justify-between items-start mb-4">
              <h4 class="font-bold text-[#2D302D] text-lg">${t.name || '-'}</h4>
              <span class="px-3 py-1 rounded-full text-xs font-bold ${colorCls}">${t.risk_percent ?? '-'}% Risk</span>
            </div>
            <div class="flex gap-4 mb-4 bg-[#FDFBF7] p-3 rounded-xl border border-[#F5EFE6]">
               <div class="flex-1 border-r border-[#E8E1D5]"><span class="text-[9px] uppercase font-bold text-[#8B7355] block mb-1">Current</span><span class="text-sm font-bold text-[#2D302D]">${t.current_value || '-'}</span></div>
               <div class="flex-1 pl-2"><span class="text-[9px] uppercase font-bold text-[#8B7355] block mb-1">Safe Range</span><span class="text-sm text-[#6D726D]">${t.safe_range || '-'}</span></div>
            </div>
            <p class="text-xs text-[#6D726D] leading-relaxed mb-4">${t.risk_reason || ''}</p>
          </div>
          ${links ? `<div class="mt-4 pt-4 border-t border-[#F5EFE6]">
                         <span class="text-[9px] uppercase font-bold text-[#8B7355] tracking-wider mb-2 block">Research Context</span>
                         ${links}
                     </div>` : ''}
        </div>
      `;
    }).join('');

    viewEl.innerHTML = `
      <div class="flex justify-between items-center mb-6">
         <h3 class="text-2xl font-bold text-[#2D302D]">Analysis Results</h3>
         <button id="btnSaveReportAction" class="px-4 py-2 bg-[#88A68B] text-white text-xs font-bold rounded-full shadow-md hover:bg-[#4D6B53] transition-colors">Save Report context to History</button>
      </div>
      ${summary}
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        ${cards}
      </div>
    `;
    unhide(viewEl);
  }

  function renderDiet(viewEl, json) {
    if (!json || typeof json !== 'object') return (viewEl.innerHTML = ''), hide(viewEl);
    const pi = json.patient_info || {};
    const lab = json.lab_analysis || {};
    const plan = json.diet_plan || {};
    const rec = json.recommendations || {};

    const patient = `
      <div class="bg-white p-6 rounded-3xl border border-[#F5EFE6] shadow-sm mb-6 flex flex-wrap gap-6">
        <div><span class="text-[10px] uppercase font-bold text-[#8B7355] tracking-widest block">Region</span><span class="font-bold text-[#2D302D]">${pi.region || '-'}</span></div>
        <div><span class="text-[10px] uppercase font-bold text-[#8B7355] tracking-widest block">Condition</span><span class="font-bold text-[#2D302D]">${pi.condition || '-'}</span></div>
        <div><span class="text-[10px] uppercase font-bold text-[#8B7355] tracking-widest block">Weight</span><span class="font-bold text-[#2D302D]">${pi.weight_kg || '-'} kg</span></div>
        <div><span class="text-[10px] uppercase font-bold text-[#8B7355] tracking-widest block">Age</span><span class="font-bold text-[#2D302D]">${pi.age || '-'}</span></div>
      </div>`;

    const days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
    const dayCards = days.filter(d => plan[d]).map(day => {
      const d = plan[day] || {};
      return `
        <div class="bg-white rounded-3xl p-6 border border-[#F5EFE6] shadow-sm hover:-translate-y-1 transition-transform">
          <div class="w-12 h-12 bg-[#88A68B]/10 rounded-2xl flex items-center justify-center text-[#4D6B53] font-bold mb-4 uppercase text-xs tracking-widest">${day.slice(0, 3)}</div>
          <div class="space-y-3">
             <div><span class="text-[10px] uppercase font-bold text-[#6B9F6F] tracking-widest block mb-1">Breakfast</span><p class="text-sm font-medium text-[#2D302D]">${d.breakfast || '-'}</p></div>
             <div><span class="text-[10px] uppercase font-bold text-[#E8956B] tracking-widest block mb-1">Lunch</span><p class="text-sm font-medium text-[#2D302D]">${d.lunch || '-'}</p></div>
             <div><span class="text-[10px] uppercase font-bold text-[#B85C3C] tracking-widest block mb-1">Dinner</span><p class="text-sm font-medium text-[#2D302D]">${d.dinner || '-'}</p></div>
             <div class="pt-2 border-t border-[#F5EFE6]"><span class="text-[10px] uppercase font-bold text-[#8B7355] tracking-widest block mb-1">Snacks</span><p class="text-xs text-[#6D726D]">${d.snacks || '-'}</p></div>
          </div>
        </div>`;
    }).join('');

    const planBlock = `
      <h3 class="text-xl font-bold text-[#2D302D] mb-4">7-Day Meal Schedule</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">${dayCards || '<p>No plan available.</p>'}</div>`;

    const list = (arr, icon, color) => Array.isArray(arr) && arr.length ? `<ul class="space-y-2">${arr.map(x => `<li class="flex items-start gap-2 text-sm text-[#2D302D]"><iconify-icon icon="${icon}" class="text-[${color}] mt-1 flex-shrink-0"></iconify-icon> <span>${x}</span></li>`).join('')}</ul>` : '<p class="text-sm text-[#6D726D]">-</p>';

    const recBlock = `
      <h3 class="text-xl font-bold text-[#2D302D] mb-4">Recommendations</h3>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-6 bg-[#FDFBF7] p-6 rounded-3xl border border-[#E8E1D5]">
        <div>
          <h4 class="font-bold text-[#6B9F6F] mb-3 uppercase tracking-widest text-[11px]">Include</h4>
          ${list(rec.foods_to_include, 'lucide:check-circle-2', '#6B9F6F')}
        </div>
        <div>
          <h4 class="font-bold text-[#B85C3C] mb-3 uppercase tracking-widest text-[11px]">Avoid</h4>
          ${list(rec.foods_to_avoid, 'lucide:x-circle', '#B85C3C')}
        </div>
        <div>
          <h4 class="font-bold text-[#D47B5A] mb-3 uppercase tracking-widest text-[11px]">Key Nutrients</h4>
          ${list(rec.key_nutrients, 'lucide:star', '#D47B5A')}
        </div>
      </div>
      <div class="mt-4 flex flex-col md:flex-row gap-4">
        ${rec.hydration ? `<div class="flex-1 bg-[#A8D5E2]/10 border border-[#A8D5E2]/30 p-4 rounded-2xl flex gap-3 items-center"><iconify-icon icon="lucide:droplets" class="text-2xl text-[#6B9CAE]"></iconify-icon> <p class="text-sm text-[#2D302D]"><strong>Hydration:</strong><br>${rec.hydration}</p></div>` : ''}
        ${rec.exercise ? `<div class="flex-1 bg-[#E8956B]/10 border border-[#E8956B]/30 p-4 rounded-2xl flex gap-3 items-center"><iconify-icon icon="lucide:activity" class="text-2xl text-[#C0693B]"></iconify-icon> <p class="text-sm text-[#2D302D]"><strong>Exercise:</strong><br>${rec.exercise}</p></div>` : ''}
      </div>`;

    viewEl.innerHTML = `${patient}${planBlock}${recBlock}`;
    unhide(viewEl);
  }

  // 1) Prescription
  const formPrescription = $('#formPrescription');
  const outPrescription = $('#outPrescription');
  const viewPrescription = $('#viewPrescription');
  if (formPrescription && outPrescription && viewPrescription) {
    const btnUploadPrescription = $('#btnUploadPrescription');
    const prescriptionFileInput = $('#prescriptionFileInput');

    if (btnUploadPrescription && prescriptionFileInput) {
      btnUploadPrescription.addEventListener('click', (e) => {
        e.preventDefault();
        prescriptionFileInput.click();
      });
      prescriptionFileInput.addEventListener('change', () => {
        if (prescriptionFileInput.files.length > 0) formPrescription.requestSubmit();
      });
    }

    formPrescription.addEventListener('submit', async (e) => {
      e.preventDefault();
      outPrescription.textContent = '⏳ Uploading — analysis running in background…';
      unhide(outPrescription);
      const fd = new FormData(formPrescription);
      try {
        const base = getBase();
        // Non-blocking: get job_id immediately
        const res = await fetch(`${base}/prescription`, { method: 'POST', body: fd });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const { job_id } = await res.json();

        outPrescription.textContent = '🔄 Analysis running in background — you can navigate to other pages.';
        showToast('Prescription analysis started. You can browse other pages.', 'processing');
        saveJob(job_id, 'prescription');

        pollJob(
          job_id,
          'prescription',
          (result) => {
            outPrescription.textContent = '';
            renderPrescription(viewPrescription, result);
            showToast('✅ Prescription analysis complete!', 'done');
            setTimeout(hideToast, 5000);
          },
          (err) => {
            outPrescription.textContent = `Error: ${err}`;
            hide(viewPrescription);
          }
        );
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
    const btnUploadHealthRisk = $('#btnUploadHealthRisk');
    const healthRiskFileInput = $('#healthRiskFileInput');

    if (btnUploadHealthRisk && healthRiskFileInput) {
      btnUploadHealthRisk.addEventListener('click', (e) => {
        e.preventDefault();
        healthRiskFileInput.click();
      });
      healthRiskFileInput.addEventListener('change', () => {
        if (healthRiskFileInput.files.length > 0) formHealthRisk.requestSubmit();
      });
    }

    formHealthRisk.addEventListener('submit', async (e) => {
      e.preventDefault();
      outHealthRisk.textContent = '⏳ Uploading — analysis running in background…';
      unhide(outHealthRisk);
      const fd = new FormData(formHealthRisk);
      try {
        const base = getBase();
        // Non-blocking: get job_id immediately
        const res = await fetch(`${base}/healthrisk`, { method: 'POST', body: fd });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const { job_id } = await res.json();

        outHealthRisk.textContent = '🔄 Analysis running in background — you can navigate to other pages.';
        showToast('Lab report analysis started. You can browse other pages.', 'processing');
        saveJob(job_id, 'labreport');

        pollJob(
          job_id,
          'labreport',
          (data) => {
            outHealthRisk.textContent = '';
            currentHealthRiskData = data;
            renderHealthRisk(viewHealthRisk, data);
            showToast('✅ Lab report analysis complete!', 'done');
            setTimeout(hideToast, 5000);

            const btnSave = $('#btnSaveReport');
            if (btnSave) unhide(btnSave);

            // Render bar chart
            const tests = Array.isArray(data.tests) ? data.tests : [];
            const labels = tests.map(t => t.name || '-');
            const values = tests.map(t => Number.isFinite(t.risk_percent) ? t.risk_percent : 0);
            const ctx = document.getElementById('expandedTrendsChart');
            if (ctx && 'Chart' in window) {
              if (riskChartInstance) riskChartInstance.destroy();
              riskChartInstance = new Chart(ctx, {
                type: 'bar',
                data: {
                  labels,
                  datasets: [{
                    label: 'Risk %', data: values,
                    backgroundColor: values.map(v => v >= 70 ? 'rgba(212,123,90,0.8)' : v >= 40 ? 'rgba(232,184,109,0.8)' : 'rgba(107,159,111,0.8)'),
                    borderRadius: 8, borderWidth: 1
                  }]
                },
                options: {
                  responsive: true,
                  plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => `${ctx.parsed.y}%` } } },
                  scales: { y: { beginAtZero: true, max: 100 }, x: {} }
                }
              });
            }
          },
          (err) => {
            outHealthRisk.textContent = `Error: ${err}`;
            hide(viewHealthRisk);
          }
        );
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
    const ctx = document.getElementById('expandedTrendsChart') || document.getElementById('trendChart');
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
            borderColor: '#6B9F6F',
            backgroundColor: '#6B9F6F20',
            tension: 0.4,
            fill: true,
            yAxisID: 'y'
          },
          {
            label: 'Risk %',
            data: riskPoints,
            borderColor: '#D47B5A',
            borderDash: [5, 5],
            tension: 0.4,
            yAxisID: 'y1'
          }
        ]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { position: 'top' }
        },
        scales: {
          x: {
            type: 'time',
            time: { unit: 'day' },
            grid: { display: false }
          },
          y: {
            type: 'linear',
            display: true,
            position: 'left',
            grid: { color: 'rgba(0,0,0,0.05)' },
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
  } else if (document.getElementById('expandedTrendsChart')) {
    // Auto load a default parameter if on the trends page
    loadTrendData('LDL_Cholesterol');
  }

  // 3) Diet Plan
  const formDiet = $('#formDiet');
  const outDiet = $('#outDiet');
  const viewDiet = $('#viewDiet');
  if (formDiet && outDiet && viewDiet) {
    formDiet.addEventListener('submit', async (e) => {
      e.preventDefault();
      outDiet.textContent = 'Generating Plan...';
      unhide(outDiet);
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

  // 3b) RAG Document Upload
  const formRagUpload = $('#formRagUpload');
  if (formRagUpload) {
    formRagUpload.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = $('#btnRagUpload');
      const originalText = btn.textContent;
      btn.textContent = 'Uploading...';
      btn.disabled = true;
      try {
        const fd = new FormData(formRagUpload);
        const base = getBase();
        const res = await fetch(`${base}/records/upload`, { method: 'POST', body: fd });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Upload failed');
        alert(data.message || 'Added to Knowledge Base!');
        formRagUpload.reset();
      } catch (err) {
        alert(`Error: ${err.message}`);
      } finally {
        btn.textContent = originalText;
        btn.disabled = false;
      }
    });
  }

  // 4) Wellbeing Chat on Home page
  const chatInput = document.getElementById('chatInput');
  const chatSubmitBtn = document.getElementById('chatSubmitBtn');
  const chatMessages = document.getElementById('chatMessages');

  function appendMsg(role, text) {
    const item = document.createElement('div');
    const contentHtml = window.markdownit ? window.markdownit().render(text) : text;

    if (role === 'user') {
      item.className = 'flex justify-end';
      item.innerHTML = `
        <div class="bg-[#E29578] text-white p-4 max-w-[85%] text-sm font-medium shadow-lg shadow-[#D47B5A]/20 rounded-[20px_20px_0px_20px]">
            ${contentHtml}
        </div>
      `;
    } else {
      const isPending = role.includes('pending');
      item.className = 'flex items-start gap-2 mb-4';
      item.innerHTML = `
        <div class="bg-white/10 text-white p-4 max-w-[85%] text-sm leading-relaxed rounded-[20px_20px_20px_0px]">
            ${isPending ? `<i>${contentHtml}</i>` : contentHtml}
        </div>
      `;
    }
    chatMessages.appendChild(item);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  async function handleChatSubmit() {
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

      const rawAns = data.answer || '';
      // Extract all graph tags
      const graphMatches = [...rawAns.matchAll(/\[GRAPH:\s*(.*?)\]/g)];
      const cleanAns = rawAns.replace(/\[GRAPH:\s*.*?\]/g, '').trim();

      appendMsg('assistant', cleanAns);

      // Render all found graphs
      if (graphMatches.length > 0) {
        for (const match of graphMatches) {
          if (match[1]) {
            await renderChatGraph(match[1].trim(), getBase());
          }
        }
      }
    } catch (err) {
      chatMessages.lastChild.remove();
      appendMsg('assistant', `Error: ${err.message}`);
    }
  }

  if (chatInput && chatSubmitBtn && chatMessages) {
    chatSubmitBtn.addEventListener('click', handleChatSubmit);
    chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') handleChatSubmit();
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

        const rawAns = data.analysis || '';
        const graphMatches = [...rawAns.matchAll(/\[GRAPH:\s*(.*?)\]/g)];
        
        // Remove the graph tags, their surrounding backticks, and bullet points
        let cleanAns = rawAns.replace(/[-*]?\s*`?\[GRAPH:\s*.*?\]`?/g, '').trim();
        // Remove enclosing markdown code blocks if the LLM still generates them
        cleanAns = cleanAns.replace(/```[a-zA-Z]*\n/gi, '').replace(/```/g, '').replace(/## Graphs/gi, '').trim();

        // Render MD
        const md = window.markdownit ? window.markdownit() : null;
        if (md) {
          summaryContent.innerHTML = md.render(cleanAns || 'No analysis returned.');
        } else {
          summaryContent.textContent = cleanAns;
          summaryContent.style.whiteSpace = 'pre-wrap';
        }
        unhide(viewSummary);

        // Render all found graphs
        if (graphMatches.length > 0) {
          for (const match of graphMatches) {
            if (match[1]) {
              await renderSummaryGraph(match[1].trim(), getBase());
            }
          }
        }
      } catch (err) {
        summaryContent.innerHTML = `<p class="error" style="color:red">Error: ${err.message}</p>`;
        unhide(viewSummary);
      } finally {
        btnLoadSummary.disabled = false;
        btnLoadSummary.textContent = 'Generate Summary';
      }
    });
  }

  async function renderSummaryGraph(metricName, base) {
    const chartId = 'summaryGraph_' + Date.now() + Math.floor(Math.random() * 100);
    const container = document.createElement('div');
    container.className = 'summary-graph-container my-6 p-4 bg-white rounded-2xl border border-[#F5EFE6] shadow-sm h-[250px]';
    container.innerHTML = `<canvas id="${chartId}"></canvas>`;

    // Append to summary content
    summaryContent.appendChild(container);

    try {
      const res = await fetch(`${base}/trends/${encodeURIComponent(metricName)}`);
      if (!res.ok) throw new Error("Data fetch failed");
      const data = await res.json();

      if (!Array.isArray(data) || data.length < 2) {
        container.innerHTML = `<small class="text-[#8B7355] italic flex items-center h-full justify-center">Not enough historical data to map a trend for ${metricName}</small>`;
        return;
      }

      const points = data.map((d, index) => {
          // Add a tiny bit of ms offset to identical timestamps to prevent chart.js overlapping failure
          return {
             x: new Date(new Date(d.timestamp).getTime() + index).toISOString(),
             y: d.value
          }
      }).sort((a,b) => new Date(a.x) - new Date(b.x));

      const ctx = document.getElementById(chartId);
      new Chart(ctx, {
        type: 'line',
        data: {
          datasets: [{
            label: metricName + ' Trend',
            data: points,
            borderColor: '#4D6B53',
            backgroundColor: 'rgba(77, 107, 83, 0.1)',
            fill: true,
            tension: 0.3,
            pointRadius: 4,
            pointBackgroundColor: '#4D6B53'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false }, title: { display: true, text: metricName + ' History', font: {family: 'Outfit', size: 16} } },
          scales: {
            x: { type: 'time', time: { tooltipFormat: 'MMM d, yyyy', displayFormats: { day: 'MMM d', hour: 'h a' } }, grid: { display: false }, ticks: { source: 'data', autoSkip: true, font: {family: 'Satoshi'} } },
            y: { beginAtZero: false, ticks: {font: {family: 'Satoshi'}} }
          }
        }
      });
    } catch (e) {
      console.error(e);
      container.remove();
    }
  }

  async function renderChatGraph(metricName, base) {
    const chartId = 'chatChart_' + Date.now();
    const container = document.createElement('div');
    container.className = 'chat-graph-container';
    container.style.marginTop = '10px';
    container.style.height = '200px';
    container.style.background = '#fff';
    container.style.borderRadius = '8px';
    container.style.padding = '5px';
    container.innerHTML = `<canvas id="${chartId}"></canvas>`;

    // Append to chat
    chatMessages.appendChild(container);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
      const res = await fetch(`${base}/trends/${encodeURIComponent(metricName)}`);
      if (!res.ok) throw new Error("Data fetch failed");
      const data = await res.json();

      if (!Array.isArray(data) || data.length < 2) {
        container.innerHTML = `<small style="color:#666; font-style:italic;">Not enough data to graph ${metricName}</small>`;
        return;
      }

      const ctx = document.getElementById(chartId);
      new Chart(ctx, {
        type: 'line',
        data: {
          labels: data.map(d => d.timestamp),
          datasets: [{
            label: metricName,
            data: data.map(d => ({ x: d.timestamp, y: d.value })),
            borderColor: '#2563eb',
            backgroundColor: 'rgba(37, 99, 235, 0.1)',
            fill: true,
            tension: 0.3,
            pointRadius: 3
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false }, title: { display: true, text: metricName } },
          scales: {
            x: { type: 'time', time: { unit: 'day' }, grid: { display: false } },
            y: { beginAtZero: false }
          }
        }
      });
    } catch (e) {
      console.error(e);
      container.remove();
    }
  }
})();

// ---------- 5. Notifications ----------
// WebSocket notifications removed — no backend endpoint available.


// 6. Medicine Queue Logic
async function loadReminders(targetEl) {
  // Use passed element or find it
  const reminderQueue = targetEl || document.getElementById('reminderQueue');
  if (!reminderQueue) {
    return; // Element not present on this page — skip silently
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
