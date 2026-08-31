const PAGE_SIZE_DEFAULT = 5;
const COOLDOWN_EVERY_DEFAULT = 15;
const COOLDOWN_SECONDS_DEFAULT = 12;

const state = {
  config: null,
  trials: [],
  page: 0,
  responses: {},
  playback: {},
  cooldownBlocksSeen: new Set(),
  startedAt: Date.now(),
  hasRenderedPage: false,
};

function qs(selector, root = document) { return root.querySelector(selector); }
function qsa(selector, root = document) { return Array.from(root.querySelectorAll(selector)); }
function setText(selector, value) { const element = qs(selector); if (element) element.textContent = value; }
function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[character]));
}
function configuredUrl(value) {
  const url = String(value || '').trim();
  return /^https?:\/\//i.test(url) ? url : '';
}
function getParams() {
  const params = new URLSearchParams(window.location.search);
  return {
    PROLIFIC_PID: params.get('PROLIFIC_PID') || '',
    STUDY_ID: params.get('STUDY_ID') || '',
    SESSION_ID: params.get('SESSION_ID') || '',
    participant: params.get('participant') || '',
  };
}
function pageSize() { return Number(state.config?.page_size) || PAGE_SIZE_DEFAULT; }
function pageCount() { return Math.ceil(state.trials.length / pageSize()); }
function currentTrials() {
  const start = state.page * pageSize();
  return state.trials.slice(start, start + pageSize());
}
function responseComplete(qid) {
  const response = state.responses[qid];
  return Boolean(response?.abx_choice && response?.confidence);
}
function completedCount() { return state.trials.filter(trial => responseComplete(trial.qid)).length; }

async function loadConfig() {
  const path = document.body.dataset.config || 'trials.json';
  const response = await fetch(path, { cache: 'no-store' });
  if (!response.ok) throw new Error(`Could not load ${path}: ${response.status}`);
  state.config = await response.json();
  state.trials = state.config.trials || [];
  if (!state.trials.length) throw new Error('No study trials were found.');
  document.title = state.config.title || 'Voice Similarity Study';
  setText('#title', document.title);
  setText('#subtitle', state.config.subtitle || 'Compare converted speech with two references.');
}

function renderTrial(trial) {
  const response = state.responses[trial.qid] || {};
  const complete = responseComplete(trial.qid) ? ' complete' : '';
  const scaleDescriptions = {
    1: 'Not confident', 3: 'Somewhat', 5: 'Quite a bit', 7: 'Extremely'
  };
  return `<article class="trial-card${complete}" data-qid="${escapeHtml(trial.qid)}">
    <div class="card-top"><div class="qid">${escapeHtml(trial.qid)}</div></div>
    <div class="reference-grid">
      <div class="audio-group">
        <span class="audio-label">Reference A</span>
        <audio controls preload="none" data-audio-role="A"><source src="${escapeHtml(trial.audio_a)}" type="audio/wav"></audio>
      </div>
      <div class="audio-group">
        <span class="audio-label">Reference B</span>
        <audio controls preload="none" data-audio-role="B"><source src="${escapeHtml(trial.audio_b)}" type="audio/wav"></audio>
      </div>
    </div>
    <div class="audio-group converted-group">
      <span class="audio-label">Converted sample X</span>
      <audio controls preload="none" data-audio-role="X"><source src="${escapeHtml(trial.audio_x)}" type="audio/wav"></audio>
    </div>
    <fieldset class="choice-fieldset">
      <legend>Which reference voice is X more similar to?</legend>
      <div class="choice-grid">
        ${['A', 'B'].map(choice => `<label class="choice-option"><input class="abx-choice" type="radio" name="${escapeHtml(trial.qid)}_choice" value="${choice}" ${response.abx_choice === choice ? 'checked' : ''}> Voice ${choice}</label>`).join('')}
      </div>
    </fieldset>
    <fieldset class="confidence-fieldset">
      <legend>How confident are you?</legend>
      <div class="confidence-grid">
        ${[1,2,3,4,5,6,7].map(value => `<label class="confidence-option"><input class="confidence-choice" type="radio" name="${escapeHtml(trial.qid)}_confidence" value="${value}" ${String(response.confidence) === String(value) ? 'checked' : ''}>${value}</label>`).join('')}
      </div>
      <div class="scale-caption">
        ${[1,2,3,4,5,6,7].map(value => `<span>${scaleDescriptions[value] || ''}</span>`).join('')}
      </div>
    </fieldset>
  </article>`;
}

function updateProgress() {
  const done = completedCount();
  setText('#progressText', `${done} / ${state.trials.length} answered`);
  const fill = qs('#progressFill');
  if (fill) fill.style.width = `${100 * done / state.trials.length}%`;
}
function updatePageCompletion() {
  const missing = currentTrials().filter(trial => !responseComplete(trial.qid)).map(trial => trial.qid);
  setText('#pageStatus', missing.length ? `Missing: ${missing.join(', ')}` : 'All samples on this page are rated.');
}
function stopOtherAudio(activeAudio) {
  qsa('audio').forEach(audio => {
    if (audio !== activeAudio && !audio.paused) audio.pause();
  });
}
function recordPlayback(event) {
  const audio = event.currentTarget;
  stopOtherAudio(audio);
  const card = audio.closest('.trial-card');
  if (!card) return;
  const qid = card.dataset.qid;
  const role = audio.dataset.audioRole;
  state.playback[qid] = state.playback[qid] || { A: 0, B: 0, X: 0 };
  state.playback[qid][role] += 1;
}
function bindPageEvents() {
  qsa('.abx-choice, .confidence-choice').forEach(element => element.addEventListener('change', onResponseChange));
  qsa('audio').forEach(audio => audio.addEventListener('play', recordPlayback));
}
function renderPage() {
  const first = state.page * pageSize() + 1;
  const last = Math.min((state.page + 1) * pageSize(), state.trials.length);
  setText('#pageLabel', `Page ${state.page + 1} of ${pageCount()}`);
  setText('#pageTitle', `Samples ${first}-${last}`);
  qs('#trialContainer').innerHTML = currentTrials().map(renderTrial).join('');
  bindPageEvents();
  qs('#backButton').disabled = state.page === 0;
  setText('#nextButton', state.page === pageCount() - 1 ? 'Review and submit' : 'Next');
  updateProgress();
  updatePageCompletion();
  if (state.hasRenderedPage) scrollToStudyTop();
  state.hasRenderedPage = true;
}
function onResponseChange(event) {
  const card = event.target.closest('.trial-card');
  const qid = card.dataset.qid;
  const choice = qs(`input[name="${CSS.escape(qid)}_choice"]:checked`);
  const confidence = qs(`input[name="${CSS.escape(qid)}_confidence"]:checked`);
  state.responses[qid] = {
    ...(state.responses[qid] || {}),
    abx_choice: choice?.value || '',
    confidence: confidence?.value || '',
    response_ts: Date.now(),
  };
  card.classList.toggle('complete', responseComplete(qid));
  updateProgress();
  updatePageCompletion();
  saveDraft();
}
function saveDraft() {
  try { localStorage.setItem(`phonostudy:${state.config.study_id}:draft`, JSON.stringify(state.responses)); } catch (error) {}
}
function loadDraft() {
  try {
    const saved = localStorage.getItem(`phonostudy:${state.config.study_id}:draft`);
    if (saved) state.responses = JSON.parse(saved) || {};
  } catch (error) {}
}
function scrollToStudyTop() {
  const anchor = qs('#studyTop');
  if (anchor) window.scrollTo({ top: anchor.getBoundingClientRect().top + window.scrollY, behavior: 'smooth' });
}
function showInstructions() {
  qs('#instructions').scrollIntoView({ behavior: 'smooth', block: 'start' });
}
function showCooldown(seconds) {
  return new Promise(resolve => {
    const overlay = qs('#cooldownOverlay');
    const timer = qs('#cooldownTimer');
    const button = qs('#cooldownContinue');
    let remaining = seconds;
    overlay.classList.remove('hidden');
    button.disabled = true;
    timer.textContent = remaining;
    const interval = setInterval(() => {
      remaining -= 1;
      timer.textContent = remaining;
      if (remaining <= 0) {
        clearInterval(interval);
        button.disabled = false;
        button.textContent = 'Continue';
      }
    }, 1000);
    button.onclick = () => {
      if (remaining > 0) return;
      overlay.classList.add('hidden');
      button.textContent = 'Please wait';
      resolve();
    };
  });
}
async function maybeCooldown(nextPage) {
  const completedSamples = (state.page + 1) * pageSize();
  const interval = Number(state.config.cooldown_every_samples) || COOLDOWN_EVERY_DEFAULT;
  if (completedSamples % interval !== 0 || nextPage >= pageCount() || state.cooldownBlocksSeen.has(completedSamples)) return;
  state.cooldownBlocksSeen.add(completedSamples);
  await showCooldown(Number(state.config.cooldown_seconds) || COOLDOWN_SECONDS_DEFAULT);
}
async function goNext() {
  if (!currentTrials().every(trial => responseComplete(trial.qid))) {
    updatePageCompletion();
    alert('Please answer all five samples on this page before continuing.');
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
  if (state.page === 0) return;
  state.page -= 1;
  renderPage();
}
function showSubmit() {
  qsa('audio').forEach(audio => audio.pause());
  qs('#instructions').classList.add('hidden');
  qs('#studySection').classList.add('hidden');
  qs('#submitSection').classList.remove('hidden');
  setText('#submitSummary', `${completedCount()} / ${state.trials.length} samples completed.`);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
function returnToRatings() {
  qs('#submitSection').classList.add('hidden');
  qs('#instructions').classList.remove('hidden');
  qs('#studySection').classList.remove('hidden');
  state.page = Math.max(0, pageCount() - 1);
  renderPage();
}
function collectPayload() {
  const postSurvey = {};
  qsa('.post-survey').forEach(element => { if (element.name) postSurvey[element.name] = element.value || ''; });
  const rows = state.trials.map(trial => {
    const response = state.responses[trial.qid] || {};
    const selectedRole = response.abx_choice === 'A' ? trial.reference_a_role : trial.reference_b_role;
    return {
      ...trial,
      condition: trial.method,
      task_type: state.config.task_type,
      abx_choice: response.abx_choice || '',
      accent_choice: response.abx_choice || '',
      selected_role: response.abx_choice ? selectedRole : '',
      is_expected_choice: response.abx_choice ? response.abx_choice === trial.expected_choice : false,
      confidence: response.confidence || '',
      response_ts: response.response_ts || '',
      playback_counts: state.playback[trial.qid] || { A: 0, B: 0, X: 0 },
    };
  });
  return {
    study_id: state.config.study_id,
    task_type: state.config.task_type,
    title: state.config.title,
    target_accent: '',
    randomized_order_seed: state.config.randomized_order_seed,
    page_size: pageSize(),
    cooldown_seconds: Number(state.config.cooldown_seconds) || COOLDOWN_SECONDS_DEFAULT,
    participant: getParams(),
    post_survey: postSurvey,
    started_at: state.startedAt,
    submitted_at: Date.now(),
    user_agent: navigator.userAgent,
    page_url: window.location.href,
    rows,
  };
}
function downloadJson(payload) {
  const participant = payload.participant.PROLIFIC_PID || payload.participant.participant || 'anonymous';
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const filename = `${payload.study_id}_${participant}_${timestamp}.json`;
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  return filename;
}
async function submitStudy() {
  if (completedCount() !== state.trials.length) {
    alert('Some samples are missing responses. Please return to the ratings.');
    return;
  }
  const button = qs('#submitButton');
  button.disabled = true;
  setText('#submitStatus', 'Submitting...');
  const payload = collectPayload();
  const endpoint = configuredUrl(state.config.response_api_url) || configuredUrl(state.config.apps_script_webapp_url);
  const completionUrl = configuredUrl(state.config.prolific_completion_url);
  try {
    if (!endpoint) throw new Error('No response API is configured');
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(`Response API returned ${response.status}`);
    try { localStorage.removeItem(`phonostudy:${state.config.study_id}:draft`); } catch (error) {}
    if (completionUrl) {
      setText('#submitStatus', 'Submitted. Redirecting to Prolific...');
      window.location.href = completionUrl;
      return;
    }
    setText('#submitStatus', 'Submitted successfully. The Prolific completion URL is not configured.');
  } catch (error) {
    const filename = downloadJson(payload);
    setText('#submitStatus', `Submission failed: ${error.message}. Local backup downloaded: ${filename}.`);
    button.disabled = false;
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  try {
    await loadConfig();
    loadDraft();
    renderPage();
    qs('#nextButton').addEventListener('click', goNext);
    qs('#backButton').addEventListener('click', goBack);
    qs('#instructionsButton').addEventListener('click', showInstructions);
    qs('#returnButton').addEventListener('click', returnToRatings);
    qs('#submitButton').addEventListener('click', submitStudy);
  } catch (error) {
    document.body.innerHTML = `<main><section class="panel"><h1>Study could not load</h1><p>${escapeHtml(error.message || error)}</p></section></main>`;
  }
});
