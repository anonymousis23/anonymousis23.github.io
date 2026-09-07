(function qualificationApp() {
  "use strict";

  const state = {
    config: null,
    formId: "",
    trials: [],
    responses: {},
    playbackCounts: {},
    startedAt: Date.now(),
    submitting: false,
  };

  const qs = (selector, root = document) => root.querySelector(selector);
  const qsa = (selector, root = document) => Array.from(root.querySelectorAll(selector));
  const setText = (selector, value) => {
    const element = qs(selector);
    if (element) element.textContent = value;
  };
  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[char]));

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

  function participantKey() {
    const participant = getParams();
    return participant.PROLIFIC_PID || participant.SESSION_ID || participant.participant || "anonymous";
  }

  function statusKey() {
    return "phonostudy:accent-qualification:" + participantKey() + ":status";
  }

  function draftKey() {
    return "phonostudy:accent-qualification:" + state.formId + ":" + participantKey() + ":draft";
  }

  function configuredUrl(value) {
    const raw = String(value || "").trim();
    if (!raw) return "";
    try { return new URL(raw, window.location.href).toString(); } catch (error) { return ""; }
  }

  function formUrl(values) {
    return configuredUrl(values && values[state.formId]);
  }

  function selectForm(formId) {
    const url = new URL(window.location.href);
    url.searchParams.set("FORM_ID", formId);
    window.location.assign(url.toString());
  }

  function showFormSelector() {
    const container = qs("#formButtons");
    container.innerHTML = state.config.form_ids.map(formId =>
      '<button class="form-button" type="button" data-form-id="' + escapeHtml(formId) + '">Form ' +
      escapeHtml(formId) + '</button>'
    ).join("");
    qsa(".form-button", container).forEach(button => {
      button.addEventListener("click", () => selectForm(button.dataset.formId));
    });
    qs("#formSelector").classList.remove("hidden");
  }

  function readStoredStatus() {
    try {
      const raw = localStorage.getItem(statusKey());
      return raw ? JSON.parse(raw) : null;
    } catch (error) {
      return null;
    }
  }

  function storeStatus(result) {
    try { localStorage.setItem(statusKey(), JSON.stringify(result)); } catch (error) {}
  }

  function saveDraft() {
    try {
      localStorage.setItem(draftKey(), JSON.stringify({
        responses: state.responses,
        playbackCounts: state.playbackCounts,
      }));
    } catch (error) {}
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

  function redirectToMain() {
    const target = configuredUrl(state.config.pass_url);
    if (!target) return;
    const url = new URL(target);
    const current = new URLSearchParams(window.location.search);
    current.forEach((value, key) => {
      if (key !== "form") url.searchParams.set(key, value);
    });
    url.searchParams.set("FORM_ID", state.formId);
    window.location.assign(url.toString());
  }

  function showResult(passed, message) {
    qs("#instructions").classList.add("hidden");
    qs("#studySection").classList.add("hidden");
    qs("#resultSection").classList.remove("hidden");
    setText("#resultTitle", passed ? "Qualification complete" : "Qualification not passed");
    setText("#resultMessage", message);
    const button = qs("#continueButton");
    button.classList.toggle("hidden", !passed);
    if (passed) button.addEventListener("click", redirectToMain, { once: true });
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function loadConfig() {
    const response = await fetch(document.body.dataset.config || "trials.json", { cache: "no-store" });
    if (!response.ok) throw new Error("Could not load qualification trials: " + response.status);
    state.config = await response.json();
    const params = getParams();
    if (!state.config.form_ids.includes(params.FORM_ID)) {
      showFormSelector();
      return false;
    }
    state.formId = params.FORM_ID;
    state.trials = state.config.trials || [];
    if (state.trials.length !== 12) throw new Error("Qualification must contain exactly 12 trials.");

    document.title = state.config.title;
    setText("#title", state.config.title);
    setText("#subtitle", state.config.subtitle);

    const previous = readStoredStatus();
    if (previous && previous.passed === true) {
      redirectToMain();
      return false;
    }
    if (previous && previous.passed === false) {
      showResult(false, "You did not meet the eligibility criteria for this study. Please return to Prolific.");
      return false;
    }

    loadDraft();
    qs("#instructions").classList.remove("hidden");
    qs("#studySection").classList.remove("hidden");
    renderTrials();
    return true;
  }

  function isAnswered(trial) {
    return Boolean(state.responses[trial.qid] && state.playbackCounts[trial.qid] > 0);
  }

  function completedCount() {
    return state.trials.filter(isAnswered).length;
  }

  function choice(trial, accent) {
    const value = accent.toLowerCase();
    const selected = state.responses[trial.qid] === value;
    return '<label class="choice"><input class="accent-choice" type="radio" name="' +
      escapeHtml(trial.qid) + '_accent" value="' + escapeHtml(value) + '"' +
      (selected ? " checked" : "") + '><span>' + escapeHtml(accent) + '</span></label>';
  }

  function trialHtml(trial) {
    const listened = state.playbackCounts[trial.qid] > 0;
    return '<article class="trial' + (isAnswered(trial) ? " complete" : "") + '" data-qid="' +
      escapeHtml(trial.qid) + '"><div class="trial-title">' + escapeHtml(trial.display_qid) +
      '</div><audio controls preload="none" data-qid="' + escapeHtml(trial.qid) +
      '"><source src="' + escapeHtml(trial.audio) + '" type="audio/wav"></audio>' +
      '<p class="play-hint">' + (listened ? "Select the primary accent." : "Play this recording to enable the choices.") +
      '</p><fieldset' + (listened ? "" : " disabled") +
      '><legend>What is the primary accent?</legend><div class="choice-grid">' +
      state.config.accent_labels.map(accent => choice(trial, accent)).join("") +
      '</div></fieldset></article>';
  }

  function renderTrials() {
    qs("#trialContainer").innerHTML = state.trials.map(trialHtml).join("");
    qsa("audio").forEach(audio => {
      audio.addEventListener("play", () => onPlay(audio));
    });
    qsa(".accent-choice").forEach(input => {
      input.addEventListener("change", onChoice);
    });
    updateProgress();
  }

  function onPlay(activeAudio) {
    qsa("audio").forEach(audio => {
      if (audio !== activeAudio && !audio.paused) audio.pause();
    });
    const qid = activeAudio.dataset.qid;
    state.playbackCounts[qid] = (state.playbackCounts[qid] || 0) + 1;
    const card = activeAudio.closest(".trial");
    const fieldset = qs("fieldset", card);
    if (fieldset) fieldset.disabled = false;
    const hint = qs(".play-hint", card);
    if (hint) hint.textContent = "Select the primary accent.";
    saveDraft();
    updateProgress();
  }

  function onChoice(event) {
    const card = event.target.closest(".trial");
    const qid = card.dataset.qid;
    state.responses[qid] = event.target.value;
    state.responses[qid + "_ts"] = Date.now();
    card.classList.toggle("complete", Boolean(state.responses[qid] && state.playbackCounts[qid] > 0));
    saveDraft();
    updateProgress();
  }

  function updateProgress() {
    const complete = completedCount();
    setText("#progressText", complete + " / " + state.trials.length + " answered");
    const fill = qs("#progressFill");
    if (fill) fill.style.width = (100 * complete / state.trials.length) + "%";
    const button = qs("#submitButton");
    if (button) button.disabled = complete !== state.trials.length || state.submitting;
    setText("#submitStatus", complete === state.trials.length
      ? "All samples are complete. Review your choices, then submit."
      : "Complete " + (state.trials.length - complete) + " remaining sample" +
        (state.trials.length - complete === 1 ? "." : "s."));
  }

  function collectPayload() {
    const participant = getParams();
    return {
      study_id: state.config.study_id,
      task_type: state.config.task_type,
      title: state.config.title,
      form_id: state.formId,
      form_assignment_basis: "url_FORM_ID",
      randomized_order_seed: state.config.randomized_order_seed,
      page_size: 12,
      participant,
      started_at: state.startedAt,
      submitted_at: Date.now(),
      user_agent: navigator.userAgent,
      page_url: window.location.href,
      rows: state.trials.map(trial => ({
        qid: trial.qid,
        display_index: trial.display_index,
        page: 1,
        condition: "natural_reference",
        condition_label: "Natural speech",
        audio: trial.audio,
        accent_choice: state.responses[trial.qid],
        primary_accent: state.responses[trial.qid],
        playback_count: state.playbackCounts[trial.qid] || 0,
        response_ts: state.responses[trial.qid + "_ts"] || null,
      })),
    };
  }

  async function submitQualification() {
    if (completedCount() !== state.trials.length || state.submitting) return;
    state.submitting = true;
    updateProgress();
    const button = qs("#submitButton");
    try {
      if (!window.PHONOSSubmission) throw new Error("Reliable submission client did not load");
      const result = await window.PHONOSSubmission.submit({
        endpoint: configuredUrl(state.config.response_api_url),
        payload: collectPayload(),
        onAttempt: (attempt, total) => setText(
          "#submitStatus", "Submitting (attempt " + attempt + " of " + total + ")..."
        ),
      });
      if (typeof result.qualification_passed !== "boolean") {
        throw new Error("The response API did not return a qualification decision");
      }
      const status = {
        passed: result.qualification_passed,
        submission_id: result.submission_id,
        completed_at: Date.now(),
      };
      storeStatus(status);
      try { localStorage.removeItem(draftKey()); } catch (error) {}

      if (result.qualification_passed) {
        showResult(true, "Your qualification was successful. Continuing to the listening study...");
        window.setTimeout(redirectToMain, 900);
      } else {
        const screenout = formUrl(state.config.screenout_completion_urls);
        showResult(false, screenout
          ? "You did not meet the eligibility criteria for this study. Redirecting to Prolific..."
          : "You did not meet the eligibility criteria for this study. Please return to Prolific.");
        if (screenout) window.setTimeout(() => window.location.assign(screenout), 1200);
      }
    } catch (error) {
      setText("#submitStatus", "Submission has not been confirmed: " + (error.message || error) +
        ". Your responses remain saved; press Submit to retry.");
      state.submitting = false;
      button.disabled = false;
    }
  }

  document.addEventListener("DOMContentLoaded", async () => {
    try {
      const loaded = await loadConfig();
      if (!loaded) return;
      qs("#instructionsButton").addEventListener("click", () => {
        qs("#instructions").scrollIntoView({ block: "start" });
      });
      qs("#submitButton").addEventListener("click", submitQualification);
    } catch (error) {
      document.body.innerHTML = '<main><section class="result"><h1>Qualification could not load</h1><p>' +
        escapeHtml(error.message || error) + '</p></section></main>';
    }
  });
})();
