const state = {
  config: null,
  formId: "",
  formAssignmentBasis: "",
  trials: [],
  page: 0,
  responses: {},
  playbackCounts: {},
  cooldownsSeen: new Set(),
  startedAt: Date.now(),
};

const qs = (selector, root = document) => root.querySelector(selector);
const qsa = (selector, root = document) => Array.from(root.querySelectorAll(selector));
const setText = (selector, value) => { const element = qs(selector); if (element) element.textContent = value; };
const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));

function getParams() {
  const params = new URLSearchParams(window.location.search);
  return {
    PROLIFIC_PID: params.get("PROLIFIC_PID") || "",
    STUDY_ID: params.get("STUDY_ID") || "",
    SESSION_ID: params.get("SESSION_ID") || "",
    FORM_ID: (params.get("FORM_ID") || params.get("form") || "").toUpperCase(),
    participant: params.get("participant") || "",
  };
}

function chooseForm(config) {
  const params = getParams();
  const forms = config.form_ids || Object.keys(config.forms || {});
  if (forms.includes(params.FORM_ID)) {
    return { id: params.FORM_ID, basis: "url_FORM_ID" };
  }
  return null;
}

function selectForm(formId) {
  const url = new URL(window.location.href);
  url.searchParams.set("FORM_ID", formId);
  window.location.assign(url.toString());
}

function showFormSelector(config) {
  const forms = config.form_ids || Object.keys(config.forms || {});
  const container = qs("#formButtons");
  container.innerHTML = forms.map(formId => '<button class="form-button" type="button" data-form-id="' + escapeHtml(formId) + '">Form ' + escapeHtml(formId) + '</button>').join("");
  qsa(".form-button", container).forEach(button => button.addEventListener("click", () => selectForm(button.dataset.formId)));
  qs("#formSelector").classList.remove("hidden");
}

function draftKey() { return `phonostudy:${state.config.study_id}:${state.formId}:draft`; }
function configuredUrl(value) { const url = String(value || "").trim(); return /^https?:\/\//i.test(url) ? url : ""; }
function pageSize() { return Number(state.config.page_size || 5); }
function pageCount() { return Math.ceil(state.trials.length / pageSize()); }
function currentTrials() { const start = state.page * pageSize(); return state.trials.slice(start, start + pageSize()); }

async function loadConfig() {
  const path = document.body.dataset.config || "forms.json";
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`Could not load ${path}: ${response.status}`);
  state.config = await response.json();
  const assignment = chooseForm(state.config);
  if (!assignment) {
    showFormSelector(state.config);
    return false;
  }
  state.formId = assignment.id;
  state.formAssignmentBasis = assignment.basis;
  state.trials = state.config.forms?.[state.formId] || [];
  if (state.trials.length !== 60) throw new Error(`Form ${state.formId} does not contain 60 trials.`);
  document.title = state.config.title || "Speech Perception Study";
  setText("#title", state.config.title || "Speech Perception Study");
  setText("#subtitle", state.config.subtitle || "Listen carefully and describe each speech sample.");
  qs("#instructions").classList.remove("hidden");
  qs("#studySection").classList.remove("hidden");
  return true;
}

function loadDraft() {
  try {
    const raw = localStorage.getItem(draftKey());
    if (!raw) return;
    const draft = JSON.parse(raw);
    state.responses = draft.responses || {};
    state.playbackCounts = draft.playbackCounts || {};
  } catch (error) {}
}

function saveDraft() {
  try { localStorage.setItem(draftKey(), JSON.stringify({ responses: state.responses, playbackCounts: state.playbackCounts })); } catch (error) {}
}

function isAnswered(qid) {
  const response = state.responses[qid];
  return Boolean(
    response?.naturalness_choice &&
    response?.primary_accent &&
    response?.secondary_accent &&
    (response.secondary_accent === "none" || response.secondary_influence)
  );
}

function completedCount() { return state.trials.filter(trial => isAnswered(trial.qid)).length; }

function choice(label, field, qid, value, selected, unavailable = false) {
  return `<label class="choice${unavailable ? " unavailable" : ""}">
    <input class="response-choice" type="radio" name="${escapeHtml(qid)}_${field}" data-field="${field}" value="${escapeHtml(value)}" ${selected ? "checked" : ""} ${unavailable ? "disabled" : ""}>
    <span>${escapeHtml(label)}</span>
  </label>`;
}

function renderTrial(trial) {
  const response = state.responses[trial.qid] || {};
  const accents = state.config.accent_labels || ["American", "British", "Indian", "Spanish"];
  const primaryReady = Boolean(response.naturalness_choice);
  const secondaryReady = Boolean(response.primary_accent);
  const influenceReady = response.secondary_accent && response.secondary_accent !== "none";
  const influenceValue = Number(response.secondary_influence || 3);
  const influenceText = response.secondary_influence ? state.config.influence_labels[String(influenceValue)] : "Choose a rating";
  return `<article class="card${isAnswered(trial.qid) ? " complete" : ""}" data-qid="${escapeHtml(trial.qid)}">
    <div class="card-top">${escapeHtml(trial.display_qid)}</div>
    <audio controls preload="none" data-qid="${escapeHtml(trial.qid)}"><source src="${escapeHtml(trial.audio)}" type="audio/wav"></audio>

    <fieldset>
      <legend><span class="step-number">1</span>Does this speech sound natural or synthetic?</legend>
      <div class="choice-grid binary">
        ${choice("Natural", "naturalness_choice", trial.qid, "natural", response.naturalness_choice === "natural")}
        ${choice("Synthetic", "naturalness_choice", trial.qid, "synthetic", response.naturalness_choice === "synthetic")}
      </div>
    </fieldset>

    <fieldset data-stage="primary" ${primaryReady ? "" : "disabled"}>
      <legend><span class="step-number">2</span>What is the primary accent?</legend>
      <div class="choice-grid">
        ${accents.map(accent => choice(accent, "primary_accent", trial.qid, accent.toLowerCase(), response.primary_accent === accent.toLowerCase())).join("")}
      </div>
    </fieldset>

    <fieldset data-stage="secondary" ${secondaryReady ? "" : "disabled"}>
      <legend><span class="step-number">3</span>Do you hear a secondary accent?</legend>
      <div class="choice-grid secondary-accent">
        ${accents.map(accent => choice(accent, "secondary_accent", trial.qid, accent.toLowerCase(), response.secondary_accent === accent.toLowerCase(), response.primary_accent === accent.toLowerCase())).join("")}
        ${choice("No secondary accent", "secondary_accent", trial.qid, "none", response.secondary_accent === "none")}
      </div>
    </fieldset>

    <fieldset data-stage="influence" class="influence-stage${influenceReady ? "" : " hidden"}">
      <legend><span class="step-number">4</span>How strongly does the secondary accent influence the speech?</legend>
      <div class="influence-panel">
        <div class="influence-endpoints"><span class="primary-endpoint">Primarily ${escapeHtml(capitalize(response.primary_accent))}</span><span class="secondary-endpoint">Strong ${escapeHtml(capitalize(response.secondary_accent))} influence</span></div>
        <div class="range-wrap"><span>1</span><input class="influence-range" type="range" min="1" max="5" step="1" value="${influenceValue}" aria-label="Secondary accent influence"><span>5</span></div>
        <div class="influence-value">${escapeHtml(influenceText)}</div>
      </div>
    </fieldset>
  </article>`;
}

function capitalize(value) { return value ? value.charAt(0).toUpperCase() + value.slice(1) : ""; }

function updateProgress() {
  const complete = completedCount();
  setText("#progressText", `${complete} / ${state.trials.length} answered`);
  setText("#pageLabel", `Page ${state.page + 1} of ${pageCount()}`);
  const fill = qs("#progressFill");
  if (fill) fill.style.width = `${100 * complete / state.trials.length}%`;
}

function updatePageStatus() {
  const missing = currentTrials().filter(trial => !isAnswered(trial.qid)).map(trial => trial.display_qid);
  setText("#pageStatus", missing.length ? `Incomplete: ${missing.join(", ")}` : "All five samples are complete.");
}

function stopOtherAudio(active) {
  qsa("audio").forEach(audio => { if (audio !== active && !audio.paused) audio.pause(); });
}

function bindPageEvents() {
  qsa(".response-choice").forEach(input => input.addEventListener("change", onChoice));
  qsa(".influence-range").forEach(input => {
    input.addEventListener("input", onInfluence);
    input.addEventListener("change", onInfluence);
  });
  qsa("audio").forEach(audio => audio.addEventListener("play", () => {
    stopOtherAudio(audio);
    const qid = audio.dataset.qid;
    state.playbackCounts[qid] = (state.playbackCounts[qid] || 0) + 1;
    saveDraft();
  }));
}

function refreshCard(card) {
  const qid = card.dataset.qid;
  const response = state.responses[qid] || {};
  const primary = qs('[data-stage="primary"]', card);
  const secondary = qs('[data-stage="secondary"]', card);
  if (primary) primary.disabled = !response.naturalness_choice;
  if (secondary) secondary.disabled = !response.primary_accent;
  qsa('input[data-field="secondary_accent"]', card).forEach(input => {
    const unavailable = input.value === response.primary_accent;
    input.disabled = unavailable;
    input.closest("label")?.classList.toggle("unavailable", unavailable);
  });
  const influence = qs('[data-stage="influence"]', card);
  const showInfluence = response.secondary_accent && response.secondary_accent !== "none";
  influence?.classList.toggle("hidden", !showInfluence);
  if (showInfluence) {
    setTextIn(card, ".primary-endpoint", `Primarily ${capitalize(response.primary_accent)}`);
    setTextIn(card, ".secondary-endpoint", `Strong ${capitalize(response.secondary_accent)} influence`);
  }
  card.classList.toggle("complete", isAnswered(qid));
  updateProgress();
  updatePageStatus();
  saveDraft();
}

function setTextIn(root, selector, value) { const element = qs(selector, root); if (element) element.textContent = value; }

function onChoice(event) {
  const card = event.target.closest(".card");
  const qid = card.dataset.qid;
  const field = event.target.dataset.field;
  const response = state.responses[qid] || {};
  response[field] = event.target.value;
  response[`${field}_ts`] = Date.now();
  if (field === "primary_accent" && response.secondary_accent === response.primary_accent) {
    response.secondary_accent = "";
    response.secondary_influence = null;
    qsa('input[data-field="secondary_accent"]', card).forEach(input => { input.checked = false; });
  }
  if (field === "secondary_accent" && response.secondary_accent === "none") response.secondary_influence = null;
  state.responses[qid] = response;
  refreshCard(card);
}

function onInfluence(event) {
  const card = event.target.closest(".card");
  const qid = card.dataset.qid;
  const response = state.responses[qid] || {};
  response.secondary_influence = Number(event.target.value);
  response.secondary_influence_ts = Date.now();
  state.responses[qid] = response;
  setTextIn(card, ".influence-value", state.config.influence_labels[String(response.secondary_influence)]);
  refreshCard(card);
}

function renderPage(scroll = true) {
  const start = state.page * pageSize();
  setText("#pageTitle", `Samples ${start + 1}-${Math.min(start + pageSize(), state.trials.length)}`);
  qs("#trialContainer").innerHTML = currentTrials().map(renderTrial).join("");
  bindPageEvents();
  qs("#backButton").disabled = state.page === 0;
  setText("#nextButton", state.page === pageCount() - 1 ? "Review and submit" : "Next");
  updateProgress();
  updatePageStatus();
  if (scroll) qs("#studyTop")?.scrollIntoView({ block: "start" });
}

function pageComplete() { return currentTrials().every(trial => isAnswered(trial.qid)); }

function showCooldown() {
  const seconds = Number(state.config.cooldown_seconds || 12);
  return new Promise(resolve => {
    const overlay = qs("#cooldownOverlay");
    const timer = qs("#cooldownTimer");
    const button = qs("#cooldownContinue");
    let remaining = seconds;
    overlay.classList.remove("hidden");
    button.disabled = true;
    button.textContent = "Please wait";
    timer.textContent = remaining;
    const interval = window.setInterval(() => {
      remaining -= 1;
      timer.textContent = Math.max(remaining, 0);
      if (remaining <= 0) {
        window.clearInterval(interval);
        button.disabled = false;
        button.textContent = "Continue";
      }
    }, 1000);
    button.onclick = () => {
      if (remaining > 0) return;
      overlay.classList.add("hidden");
      resolve();
    };
  });
}

async function goNext() {
  if (!pageComplete()) {
    updatePageStatus();
    window.alert("Please complete all four judgments for each sample on this page.");
    return;
  }
  const nextPage = state.page + 1;
  if (nextPage >= pageCount()) return showSubmit();
  const completedSamples = nextPage * pageSize();
  const interval = Number(state.config.cooldown_every_samples || 15);
  if (completedSamples % interval === 0 && !state.cooldownsSeen.has(completedSamples)) {
    state.cooldownsSeen.add(completedSamples);
    await showCooldown();
  }
  state.page = nextPage;
  renderPage(true);
}

function goBack() {
  if (state.page === 0) return;
  state.page -= 1;
  renderPage(true);
}

function showSubmit() {
  qs("#instructions").classList.add("hidden");
  qs("#studySection").classList.add("hidden");
  qs("#submitSection").classList.remove("hidden");
  setText("#submitSummary", `${completedCount()} of ${state.trials.length} samples completed.`);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function returnToRatings() {
  qs("#submitSection").classList.add("hidden");
  qs("#instructions").classList.remove("hidden");
  qs("#studySection").classList.remove("hidden");
  state.page = pageCount() - 1;
  renderPage(true);
}

function collectPayload() {
  const participant = getParams();
  const postSurvey = {};
  qsa(".post-survey").forEach(element => { if (element.name) postSurvey[element.name] = element.value || ""; });
  const rows = state.trials.map(trial => {
    const response = state.responses[trial.qid] || {};
    return {
      ...trial,
      naturalness_choice: response.naturalness_choice || "",
      naturalness_correct: response.naturalness_choice === trial.expected_naturalness,
      primary_accent: response.primary_accent || "",
      primary_accent_correct: response.primary_accent === trial.expected_primary_accent,
      secondary_accent: response.secondary_accent || "",
      secondary_influence: response.secondary_accent === "none" ? null : response.secondary_influence || null,
      accent_choice: response.primary_accent || "",
      playback_count: state.playbackCounts[trial.qid] || 0,
      naturalness_response_ts: response.naturalness_choice_ts || null,
      primary_response_ts: response.primary_accent_ts || null,
      secondary_response_ts: response.secondary_accent_ts || null,
      influence_response_ts: response.secondary_influence_ts || null,
      response_ts: Math.max(response.naturalness_choice_ts || 0, response.primary_accent_ts || 0, response.secondary_accent_ts || 0, response.secondary_influence_ts || 0),
    };
  });
  return {
    study_id: state.config.study_id,
    task_type: state.config.task_type,
    title: state.config.title,
    form_id: state.formId,
    form_assignment_basis: state.formAssignmentBasis,
    randomized_order_seed: state.config.randomized_order_seed,
    page_size: pageSize(),
    cooldown_seconds: state.config.cooldown_seconds,
    participant,
    post_survey: postSurvey,
    started_at: state.startedAt,
    submitted_at: Date.now(),
    user_agent: navigator.userAgent,
    page_url: window.location.href,
    rows,
  };
}

function downloadBackup(payload) {
  const id = payload.participant.PROLIFIC_PID || payload.participant.participant || "anonymous";
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const filename = `${payload.study_id}_${id}_${stamp}.json`;
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  return filename;
}

async function submitStudy() {
  if (completedCount() !== state.trials.length) return window.alert("Please complete every sample before submitting.");
  const button = qs("#submitButton");
  button.disabled = true;
  setText("#submitStatus", "Submitting...");
  const payload = collectPayload();
  const endpoint = configuredUrl(state.config.response_api_url);
  const completionUrl = configuredUrl(state.config.prolific_completion_url);
  try {
    if (!endpoint) throw new Error("Response API is not configured");
    const response = await fetch(endpoint, { method: "POST", headers: {"Content-Type":"application/json"}, body: JSON.stringify(payload) });
    if (!response.ok) throw new Error(`Response API returned ${response.status}`);
    try { localStorage.removeItem(draftKey()); } catch (error) {}
    if (completionUrl) {
      setText("#submitStatus", "Submitted. Redirecting to Prolific...");
      window.location.href = completionUrl;
      return;
    }
    setText("#submitStatus", "Submitted successfully. The Prolific completion URL is not configured; please contact the study organizer.");
  } catch (error) {
    const filename = downloadBackup(payload);
    setText("#submitStatus", `Upload failed. Local backup downloaded: ${filename}. Please contact the study organizer.`);
    button.disabled = false;
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  try {
    const formLoaded = await loadConfig();
    if (!formLoaded) return;
    loadDraft();
    renderPage(false);
    qs("#nextButton").addEventListener("click", goNext);
    qs("#backButton").addEventListener("click", goBack);
    qs("#instructionsButton").addEventListener("click", () => qs("#instructions")?.scrollIntoView({ block: "start" }));
    qs("#returnButton").addEventListener("click", returnToRatings);
    qs("#submitButton").addEventListener("click", submitStudy);
  } catch (error) {
    document.body.innerHTML = `<main><section class="post"><h1>Study could not load</h1><p>${escapeHtml(error.message || error)}</p></section></main>`;
  }
});
