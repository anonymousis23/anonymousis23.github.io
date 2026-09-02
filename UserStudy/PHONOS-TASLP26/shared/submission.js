(function attachReliableSubmission(global) {
  "use strict";

  const RETRY_DELAYS_MS = [0, 1000, 3000, 7000];
  const REQUEST_TIMEOUT_MS = 20000;

  function participantKey(payload) {
    const participant = payload.participant || {};
    return participant.PROLIFIC_PID || participant.SESSION_ID || participant.participant || "anonymous";
  }

  function storageKey(payload) {
    const form = payload.form_id || "default";
    return `phonostudy:${payload.study_id}:${form}:${participantKey(payload)}:pending-submission`;
  }

  function newSubmissionId() {
    if (global.crypto && typeof global.crypto.randomUUID === "function") {
      return global.crypto.randomUUID();
    }
    return `${Date.now().toString(36)}_${Math.random().toString(36).slice(2)}_${Math.random().toString(36).slice(2)}`;
  }

  function readPending(payload) {
    try {
      const saved = global.localStorage.getItem(storageKey(payload));
      if (!saved) return null;
      const parsed = JSON.parse(saved);
      return parsed && parsed.payload && parsed.payload.study_id === payload.study_id ? parsed : null;
    } catch (error) {
      return null;
    }
  }

  function persist(payload) {
    try {
      global.localStorage.setItem(storageKey(payload), JSON.stringify({ saved_at: Date.now(), payload }));
      return true;
    } catch (error) {
      return false;
    }
  }

  function clearPending(payload) {
    try { global.localStorage.removeItem(storageKey(payload)); } catch (error) {}
  }

  function sleep(milliseconds) {
    return new Promise(resolve => global.setTimeout(resolve, milliseconds));
  }

  async function postOnce(endpoint, payload) {
    const controller = new AbortController();
    const timeout = global.setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
    try {
      const response = await global.fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
      let data = {};
      try { data = await response.json(); } catch (error) {}
      if (!response.ok) {
        const failure = new Error(data.detail || `Response API returned ${response.status}`);
        failure.status = response.status;
        throw failure;
      }
      if (!data.ok || data.submission_id !== payload.submission_id) {
        throw new Error("The response API did not confirm the submission identifier");
      }
      return data;
    } finally {
      global.clearTimeout(timeout);
    }
  }

  function retryable(error) {
    const status = Number(error && error.status) || 0;
    return status === 0 || status === 408 || status === 425 || status === 429 || status >= 500;
  }

  async function submit(options) {
    const endpoint = String(options.endpoint || "").trim();
    if (!/^https?:\/\//i.test(endpoint)) throw new Error("No valid response API is configured");

    const candidate = JSON.parse(JSON.stringify(options.payload || {}));
    const existing = readPending(candidate);
    const payload = existing ? existing.payload : candidate;
    if (!payload.submission_id) payload.submission_id = newSubmissionId();
    const pendingPersisted = persist(payload);

    let lastError = null;
    for (let index = 0; index < RETRY_DELAYS_MS.length; index += 1) {
      const delay = RETRY_DELAYS_MS[index];
      if (delay) await sleep(delay);
      if (typeof options.onAttempt === "function") {
        options.onAttempt(index + 1, RETRY_DELAYS_MS.length);
      }
      try {
        const result = await postOnce(endpoint, payload);
        clearPending(payload);
        return { ...result, pending_persisted: pendingPersisted };
      } catch (error) {
        lastError = error;
        if (!retryable(error)) break;
      }
    }

    lastError = lastError || new Error("Submission failed");
    lastError.pendingPersisted = pendingPersisted;
    throw lastError;
  }

  global.PHONOSSubmission = { submit };
})(window);
