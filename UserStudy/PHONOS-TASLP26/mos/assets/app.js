const DEFAULT_RESPONSE_API_URL = "";
const DEFAULT_APPS_SCRIPT_WEBAPP_URL = "";
const DEFAULT_PROLIFIC_COMPLETION_URL = "";
const PAGE_SIZE = 5;
const COOLDOWN_EVERY_PAGES = 3;
const COOLDOWN_SECONDS = 12;

const state = {
  config: null,
  trials: [],
  page: 0,
  responses: {},
  cooldownPagesSeen: new Set(),
  startedAt: Date.now(),
};

function qs(sel, root = document) { return root.querySelector(sel); }
function qsa(sel, root = document) { return Array.from(root.querySelectorAll(sel)); }
function setText(sel, value) { const el = qs(sel); if (el) el.textContent = value; }
function setHtml(sel, value) { const el = qs(sel); if (el) el.innerHTML = value; }
function setDisabled(sel, value) { const el = qs(sel); if (el) el.disabled = value; }
function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
function configuredUrl(value, fallback = '') {
  const url = String(value || fallback || '').trim();
  return /^https?:\/\//i.test(url) ? url : '';
}
function getParams() {
  const p = new URLSearchParams(window.location.search);
  return {
    PROLIFIC_PID: p.get('PROLIFIC_PID') || '',
    STUDY_ID: p.get('STUDY_ID') || '',
    SESSION_ID: p.get('SESSION_ID') || '',
    participant: p.get('participant') || '',
  };
}

async function loadConfig() {
  const configPath = document.body.dataset.config || 'trials.json';
  const resp = await fetch(configPath, { cache: 'no-store' });
  if (!resp.ok) throw new Error(`Could not load ${configPath}: ${resp.status}`);
  const config = await resp.json();
  state.config = config;
  state.trials = config.trials || [];
  document.title = config.title || 'PHONOS MOS Listening Test';
  setText('#title', config.title || 'Audio Quality Evaluation');
  setText('#subtitle', config.subtitle || 'Please listen carefully and rate the audio quality of each clip.');
  renderReferences();
  loadLocalDraft();
  renderPage();
}

function mosScale() {
  return state.config?.mos_scale || [
    { value: 5, label: 'Excellent', distortion: 'Imperceptible' },
    { value: 4, label: 'Good', distortion: 'Just perceptible, but not annoying' },
    { value: 3, label: 'Fair', distortion: 'Perceptible and slightly annoying' },
    { value: 2, label: 'Poor', distortion: 'Annoying, but not objectionable' },
    { value: 1, label: 'Bad', distortion: 'Very annoying and objectionable' },
  ];
}

function renderReferences() {
  const rows = state.config?.reference_samples || [];
  const container = qs('#referenceSamples');
  if (!container) return;
  container.innerHTML = `<table class="reference-table">
    <thead>
      <tr>
        <th>Audio quality</th>
        <th>Level of distortion</th>
        <th>Reference Clip A</th>
        <th>Reference Clip B</th>
      </tr>
    </thead>
    <tbody>
      ${rows.map(row => `<tr>
        <td>${escapeHtml(row.label)}</td>
        <td>${escapeHtml(row.distortion)}</td>
        <td><audio controls preload="none"><source src="${escapeHtml(row.clip_a)}" type="audio/wav"></audio></td>
        <td><audio controls preload="none"><source src="${escapeHtml(row.clip_b)}" type="audio/wav"></audio></td>
      </tr>`).join('')}
    </tbody>
  </table>`;
}

function pageCount() { return Math.ceil(state.trials.length / PAGE_SIZE); }
function currentTrials() {
  const start = state.page * PAGE_SIZE;
  return state.trials.slice(start, start + PAGE_SIZE);
}
function isAnswered(trialId) {
  const r = state.responses[trialId];
  return Boolean(r && r.mos_rating);
}
function completedCount() { return state.trials.filter(t => isAnswered(t.qid)).length; }

function updateProgress() {
  const done = completedCount();
  const total = state.trials.length;
  setText('#progressText', `${done} / ${total} answered`);
  const fill = qs('#progressFill');
  if (fill) fill.style.width = `${total ? 100 * done / total : 0}%`;
}

function renderPage() {
  const trials = currentTrials();
  const container = qs('#trialContainer');
  const pageTotal = pageCount();
  setText('#pageLabel', `Page ${state.page + 1} of ${pageTotal}`);
  setText('#pageTitle', `Samples ${state.page * PAGE_SIZE + 1}-${Math.min((state.page + 1) * PAGE_SIZE, state.trials.length)}`);
  if (!container) return;
  container.innerHTML = trials.map(renderTrial).join('');
  qsa('.mos-choice').forEach(el => el.addEventListener('change', onResponseChange));
  setDisabled('#backButton', state.page === 0);
  setText('#nextButton', state.page === pageTotal - 1 ? 'Review and submit' : 'Next');
  updateProgress();
  updatePageCompletion();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function renderTrial(t) {
  const r = state.responses[t.qid] || {};
  const complete = isAnswered(t.qid) ? ' complete' : '';
  return `<article class="card${complete}" data-qid="${escapeHtml(t.qid)}">
    <div class="card-top">
      <div class="qid">${escapeHtml(t.qid)}</div>
    </div>
    <audio controls preload="none"><source src="${escapeHtml(t.audio)}" type="audio/wav"></audio>
    <fieldset class="mos-fieldset">
      <legend>Rate the audio quality</legend>
      <div class="mos-grid" role="radiogroup" aria-label="MOS rating for ${escapeHtml(t.qid)}">
        ${mosScale().map(item => `<label class="mos-option">
          <input class="mos-choice" type="radio" name="${escapeHtml(t.qid)}_mos" value="${item.value}" ${String(r.mos_rating) === String(item.value) ? 'checked' : ''}>
          <span class="mos-value">${escapeHtml(item.value)}</span>
          <span class="mos-label">${escapeHtml(item.label)}</span>
          <span class="mos-desc">${escapeHtml(item.distortion)}</span>
        </label>`).join('')}
      </div>
    </fieldset>
  </article>`;
}

function onResponseChange(event) {
  const card = event.target.closest('.card');
  const qid = card.dataset.qid;
  const selected = qs(`input[name="${CSS.escape(qid)}_mos"]:checked`);
  const scaleItem = mosScale().find(x => String(x.value) === String(selected?.value));
  state.responses[qid] = {
    ...(state.responses[qid] || {}),
    mos_rating: selected ? selected.value : '',
    mos_label: scaleItem?.label || '',
    distortion_label: scaleItem?.distortion || '',
    response_ts: Date.now(),
  };
  card.classList.toggle('complete', isAnswered(qid));
  updateProgress();
  updatePageCompletion();
  saveLocalDraft();
}

function updatePageCompletion() {
  const missing = currentTrials().filter(t => !isAnswered(t.qid)).map(t => t.qid);
  setText('#pageStatus', missing.length ? `Missing: ${missing.join(', ')}` : 'All samples on this page are rated.');
}
function pageComplete() { return currentTrials().every(t => isAnswered(t.qid)); }

function saveLocalDraft() {
  try { localStorage.setItem(`phonostudy:${state.config.study_id}:draft`, JSON.stringify(state.responses)); } catch (e) {}
}
function loadLocalDraft() {
  try {
    const raw = localStorage.getItem(`phonostudy:${state.config.study_id}:draft`);
    if (raw) state.responses = JSON.parse(raw) || {};
  } catch (e) {}
}

function maybeCooldown(nextPage) {
  const completedPageNumber = state.page + 1;
  const shouldCooldown = completedPageNumber % COOLDOWN_EVERY_PAGES === 0 && nextPage < pageCount() && !state.cooldownPagesSeen.has(completedPageNumber);
  if (!shouldCooldown) return Promise.resolve();
  state.cooldownPagesSeen.add(completedPageNumber);
  return showCooldown(COOLDOWN_SECONDS);
}

function showCooldown(seconds) {
  return new Promise(resolve => {
    const overlay = qs('#cooldownOverlay');
    const timer = qs('#cooldownTimer');
    const btn = qs('#cooldownContinue');
    let left = seconds;
    overlay.classList.remove('hidden');
    if (btn) btn.disabled = true;
    if (timer) timer.textContent = left;
    const interval = setInterval(() => {
      left -= 1;
      if (timer) timer.textContent = left;
      if (left <= 0) {
        clearInterval(interval);
        if (btn) btn.disabled = false;
        if (btn) btn.textContent = 'Continue';
      }
    }, 1000);
    btn.onclick = () => {
      if (left > 0) return;
      overlay.classList.add('hidden');
      if (btn) btn.textContent = 'Please wait';
      resolve();
    };
  });
}

async function goNext() {
  if (!pageComplete()) {
    updatePageCompletion();
    alert('Please rate all five samples on this page before continuing.');
    return;
  }
  const nextPage = state.page + 1;
  if (nextPage < pageCount()) {
    await maybeCooldown(nextPage);
    state.page = nextPage;
    renderPage();
  } else {
    showSubmit();
  }
}

function goBack() {
  if (state.page > 0) {
    state.page -= 1;
    qs('#submitSection')?.classList.add('hidden');
    qs('#studySection')?.classList.remove('hidden');
    renderPage();
  }
}

function showSubmit() {
  qs('#studySection')?.classList.add('hidden');
  qs('#submitSection')?.classList.remove('hidden');
  setText('#submitSummary', `${completedCount()} / ${state.trials.length} samples rated.`);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function collectPayload() {
  const post = {};
  qsa('.post-survey').forEach(el => { if (el.name) post[el.name] = el.value || ''; });
  const params = getParams();
  const rows = state.trials.map(t => ({
    ...t,
    mos_rating: state.responses[t.qid]?.mos_rating || '',
    mos_label: state.responses[t.qid]?.mos_label || '',
    distortion_label: state.responses[t.qid]?.distortion_label || '',
    response_ts: state.responses[t.qid]?.response_ts || '',
  }));
  return {
    study_id: state.config.study_id,
    task_type: state.config.task_type || 'mos',
    title: state.config.title,
    target_accent: state.config.target_accent || '',
    randomized_order_seed: state.config.randomized_order_seed,
    page_size: PAGE_SIZE,
    cooldown_seconds: COOLDOWN_SECONDS,
    participant: params,
    post_survey: post,
    started_at: state.startedAt,
    submitted_at: Date.now(),
    user_agent: navigator.userAgent,
    page_url: window.location.href,
    submission_endpoint: configuredUrl(state.config.response_api_url, DEFAULT_RESPONSE_API_URL) || configuredUrl(state.config.apps_script_webapp_url, DEFAULT_APPS_SCRIPT_WEBAPP_URL),
    prolific_completion_url: configuredUrl(state.config.prolific_completion_url, DEFAULT_PROLIFIC_COMPLETION_URL),
    rows,
  };
}

function downloadJson(payload) {
  const id = payload.participant.PROLIFIC_PID || payload.participant.participant || 'anonymous';
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const filename = `${payload.study_id}_${id}_${stamp}.json`;
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  return filename;
}

async function submitToResponseApi(payload) {
  const endpoint = configuredUrl(state.config.response_api_url, DEFAULT_RESPONSE_API_URL) || configuredUrl(state.config.apps_script_webapp_url, DEFAULT_APPS_SCRIPT_WEBAPP_URL);
  if (!endpoint) return false;
  const resp = await fetch(endpoint, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload),
    keepalive: true,
  });
  if (!resp.ok) throw new Error(`Response API returned ${resp.status}`);
  return true;
}

async function submitStudy() {
  if (completedCount() !== state.trials.length) {
    alert('Some samples are still missing ratings. Please go back and complete them.');
    return;
  }
  const payload = collectPayload();
  setDisabled('#submitButton', true);
  setText('#submitStatus', 'Submitting...');
  let apiOk = false;
  try {
    apiOk = await submitToResponseApi(payload);
  } catch (err) {
    console.error(err);
    setText('#submitStatus', `API submission failed: ${err.message}. A local backup will download now.`);
  }
  const filename = downloadJson(payload);
  const backup = qs('#backupBox');
  if (backup) {
    backup.classList.remove('hidden');
    backup.textContent = `Local backup downloaded: ${filename}\n\nKeep this file if the browser does not redirect automatically.`;
  }
  if (apiOk) {
    setText('#submitStatus', 'Submitted. A local backup was also downloaded.');
    localStorage.removeItem(`phonostudy:${state.config.study_id}:draft`);
  } else if (!payload.submission_endpoint) {
    setText('#submitStatus', 'No response API is configured. A local backup was downloaded.');
  }
  const completion = configuredUrl(state.config.prolific_completion_url, DEFAULT_PROLIFIC_COMPLETION_URL);
  if (completion && apiOk) {
    setTimeout(() => { window.location.href = completion; }, 900);
  } else {
    setDisabled('#submitButton', false);
  }
}

function reviewStudy() {
  qs('#submitSection')?.classList.add('hidden');
  qs('#studySection')?.classList.remove('hidden');
  state.page = Math.max(0, pageCount() - 1);
  renderPage();
}

document.addEventListener('DOMContentLoaded', () => {
  qs('#nextButton')?.addEventListener('click', goNext);
  qs('#backButton')?.addEventListener('click', goBack);
  qs('#submitButton')?.addEventListener('click', submitStudy);
  qs('#reviewButton')?.addEventListener('click', reviewStudy);
  loadConfig().catch(err => {
    console.error(err);
    setHtml('#trialContainer', `<div class="notice"><strong>Study could not load</strong><br>${escapeHtml(err.message)}</div>`);
  });
});
