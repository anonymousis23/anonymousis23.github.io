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
function getParams() {
  const p = new URLSearchParams(window.location.search);
  return {
    PROLIFIC_PID: p.get('PROLIFIC_PID') || '',
    STUDY_ID: p.get('STUDY_ID') || '',
    SESSION_ID: p.get('SESSION_ID') || '',
    participant: p.get('participant') || '',
  };
}
function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
}
function configuredUrl(value, fallback = '') {
  const url = String(value || fallback || '').trim();
  return /^https?:\/\//i.test(url) ? url : '';
}
async function loadConfig() {
  const configPath = document.body.dataset.config || 'trials.json';
  const resp = await fetch(configPath, { cache: 'no-store' });
  if (!resp.ok) throw new Error(`Could not load ${configPath}: ${resp.status}`);
  const config = await resp.json();
  state.config = config;
  state.trials = config.trials || [];
  document.title = config.title || 'Accent Verification Study';
  qs('#title').textContent = config.title || 'Accent Verification Study';
  qs('#subtitle').textContent = config.subtitle || 'Accent verification listening study';
  qs('#choiceA').textContent = config.choice_labels?.[0] || 'American';
  qs('#choiceB').textContent = config.choice_labels?.[1] || 'Target accent';
  if (qs('#totalCount')) qs('#totalCount').textContent = state.trials.length;
  if (qs('#pageSize')) qs('#pageSize').textContent = PAGE_SIZE;
  if (qs('#cooldownEvery')) qs('#cooldownEvery').textContent = PAGE_SIZE * COOLDOWN_EVERY_PAGES;
  renderPage();
}
function pageCount() { return Math.ceil(state.trials.length / PAGE_SIZE); }
function currentTrials() {
  const start = state.page * PAGE_SIZE;
  return state.trials.slice(start, start + PAGE_SIZE);
}
function isAnswered(trialId) {
  const r = state.responses[trialId];
  return Boolean(r && r.accent_choice && r.confidence);
}
function completedCount() { return state.trials.filter(t => isAnswered(t.qid)).length; }
function updateProgress() {
  const done = completedCount();
  const total = state.trials.length;
  qs('#progressText').textContent = `${done} / ${total} answered`;
  qs('#progressFill').style.width = `${total ? 100 * done / total : 0}%`;
}
function renderPage() {
  const trials = currentTrials();
  const container = qs('#trialContainer');
  const pageTotal = pageCount();
  qs('#pageLabel').textContent = `Page ${state.page + 1} of ${pageTotal}`;
  qs('#pageTitle').textContent = `Samples ${state.page * PAGE_SIZE + 1}-${Math.min((state.page + 1) * PAGE_SIZE, state.trials.length)}`;
  container.innerHTML = trials.map(renderTrial).join('');
  qsa('.accent-choice').forEach(el => el.addEventListener('change', onResponseChange));
  qsa('.confidence-choice').forEach(el => el.addEventListener('change', onResponseChange));
  qs('#backButton').disabled = state.page === 0;
  qs('#nextButton').textContent = state.page === pageTotal - 1 ? 'Review and submit' : 'Next';
  updateProgress();
  updatePageCompletion();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
function renderTrial(t) {
  const r = state.responses[t.qid] || {};
  const choices = state.config.choice_labels || ['American', state.config.target_accent || 'Target accent'];
  const complete = isAnswered(t.qid) ? ' complete' : '';
  return `<article class="card${complete}" data-qid="${escapeHtml(t.qid)}">
    <div class="card-top">
      <div class="qid">${escapeHtml(t.qid)}</div>
    </div>
    <audio controls preload="none"><source src="${escapeHtml(t.audio)}" type="audio/wav"></audio>
    <div class="choice-grid" role="radiogroup" aria-label="Accent choice for ${escapeHtml(t.qid)}">
      ${choices.map(label => `<label class="choice"><input class="accent-choice" type="radio" name="${escapeHtml(t.qid)}_accent" value="${escapeHtml(label)}" ${r.accent_choice === label ? 'checked' : ''}> ${escapeHtml(label)}</label>`).join('')}
    </div>
    <fieldset class="confidence">
      <legend>How confident are you?</legend>
      <div class="conf-grid">
        ${[1,2,3,4,5,6,7].map(v => `<label><input class="confidence-choice" type="radio" name="${escapeHtml(t.qid)}_confidence" value="${v}" ${String(r.confidence) === String(v) ? 'checked' : ''}>${v}</label>`).join('')}
      </div>
      <div class="scale-caption"><span>1 = not confident</span><span>7 = extremely confident</span></div>
    </fieldset>
  </article>`;
}
function onResponseChange(event) {
  const card = event.target.closest('.card');
  const qid = card.dataset.qid;
  const accent = qs(`input[name="${CSS.escape(qid)}_accent"]:checked`);
  const conf = qs(`input[name="${CSS.escape(qid)}_confidence"]:checked`);
  state.responses[qid] = {
    ...(state.responses[qid] || {}),
    accent_choice: accent ? accent.value : '',
    confidence: conf ? conf.value : '',
    response_ts: Date.now(),
  };
  card.classList.toggle('complete', isAnswered(qid));
  updateProgress();
  updatePageCompletion();
  saveLocalDraft();
}
function updatePageCompletion() {
  const missing = currentTrials().filter(t => !isAnswered(t.qid)).map(t => t.qid);
  qs('#pageStatus').textContent = missing.length ? `Missing: ${missing.join(', ')}` : 'All samples on this page are rated.';
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
    btn.disabled = true;
    timer.textContent = left;
    const interval = setInterval(() => {
      left -= 1;
      timer.textContent = left;
      if (left <= 0) {
        clearInterval(interval);
        btn.disabled = false;
        btn.textContent = 'Continue';
      }
    }, 1000);
    btn.onclick = () => {
      if (left > 0) return;
      overlay.classList.add('hidden');
      btn.textContent = 'Please wait';
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
    qs('#submitSection').classList.add('hidden');
    qs('#studySection').classList.remove('hidden');
    renderPage();
  }
}
function showSubmit() {
  qs('#studySection').classList.add('hidden');
  qs('#submitSection').classList.remove('hidden');
  qs('#submitSummary').textContent = `${completedCount()} / ${state.trials.length} samples rated.`;
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
function collectPayload() {
  const post = {};
  qsa('.post-survey').forEach(el => { if (el.name) post[el.name] = el.value || ''; });
  const params = getParams();
  const rows = state.trials.map(t => ({
    ...t,
    accent_choice: state.responses[t.qid]?.accent_choice || '',
    confidence: state.responses[t.qid]?.confidence || '',
    response_ts: state.responses[t.qid]?.response_ts || '',
  }));
  return {
    study_id: state.config.study_id,
    title: state.config.title,
    target_accent: state.config.target_accent,
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
  const btn = qs('#submitButton');
  const status = qs('#submitStatus');
  btn.disabled = true;
  status.textContent = 'Preparing response file...';
  const payload = collectPayload();
  let uploaded = false;
  let uploadError = null;
  try {
    uploaded = await submitToResponseApi(payload);
  } catch (e) {
    uploadError = e;
  }

  const filename = downloadJson(payload);
  try { localStorage.removeItem(`phonostudy:${state.config.study_id}:draft`); } catch(e) {}

  if (uploaded) {
    status.textContent = `Saved to server and downloaded backup ${filename}.`;
    const completionUrl = configuredUrl(state.config.prolific_completion_url, DEFAULT_PROLIFIC_COMPLETION_URL);
    if (completionUrl) window.location.href = completionUrl;
  } else if (uploadError) {
    status.textContent = `Server upload failed, but downloaded backup ${filename}. Please keep this file.`;
    alert(`Server upload failed, but your responses were downloaded as ${filename}. Details: ${uploadError.message || uploadError}`);
    btn.disabled = false;
  } else {
    status.textContent = `Downloaded ${filename}. Please keep this file for upload if requested.`;
    btn.disabled = false;
  }
}
document.addEventListener('DOMContentLoaded', async () => {
  try {
    await loadConfig();
    loadLocalDraft();
    renderPage();
    qs('#nextButton').addEventListener('click', goNext);
    qs('#backButton').addEventListener('click', goBack);
    qs('#submitButton').addEventListener('click', submitStudy);
    qs('#returnButton').addEventListener('click', () => {
      qs('#submitSection').classList.add('hidden');
      qs('#studySection').classList.remove('hidden');
      state.page = Math.max(0, pageCount() - 1);
      renderPage();
    });
  } catch (e) {
    document.body.innerHTML = `<main><section class="panel"><h1>Study could not load</h1><p>${escapeHtml(e.message || e)}</p></section></main>`;
  }
});
