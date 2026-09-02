"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const stored = new Map();
const localStorage = {
  getItem: key => stored.has(key) ? stored.get(key) : null,
  setItem: (key, value) => stored.set(key, value),
  removeItem: key => stored.delete(key),
};

let idCounter = 0;
let shouldFail = true;
const posted = [];
const window = {
  localStorage,
  crypto: {
    randomUUID: () => `00000000-0000-4000-8000-${String(++idCounter).padStart(12, "0")}`,
  },
  setTimeout: callback => {
    callback();
    return 1;
  },
  clearTimeout: () => {},
  fetch: async (_endpoint, options) => {
    const payload = JSON.parse(options.body);
    posted.push(payload);
    if (shouldFail) throw new Error("simulated network failure");
    return {
      ok: true,
      status: 200,
      json: async () => ({
        ok: true,
        submission_id: payload.submission_id,
        rows: payload.rows.length,
        duplicate: false,
      }),
    };
  },
};

const context = { window, AbortController };
vm.createContext(context);
vm.runInContext(
  fs.readFileSync(path.join(__dirname, "submission.js"), "utf8"),
  context,
);

function payload(formId) {
  return {
    study_id: "phonos_taslp26_accent_multidimensional",
    form_id: formId,
    participant: { PROLIFIC_PID: "same-browser-participant" },
    rows: [{ qid: `${formId}001` }],
  };
}

async function expectFailure(formId) {
  try {
    await window.PHONOSSubmission.submit({
      endpoint: "https://example.test/api/submissions",
      payload: payload(formId),
    });
    assert.fail(`Form ${formId} unexpectedly succeeded`);
  } catch (error) {
    assert.strictEqual(error.pendingPersisted, true);
  }
}

async function main() {
  await expectFailure("A");
  await expectFailure("B");

  const pending = [...stored.entries()].map(([key, value]) => [key, JSON.parse(value)]);
  assert.strictEqual(pending.length, 2);
  const formA = pending.find(([key]) => key.includes(":A:"));
  const formB = pending.find(([key]) => key.includes(":B:"));
  assert(formA && formB, "Forms A and B must use separate storage keys");
  assert.notStrictEqual(
    formA[1].payload.submission_id,
    formB[1].payload.submission_id,
    "Forms A and B must use different submission IDs",
  );

  shouldFail = false;
  const resultA = await window.PHONOSSubmission.submit({
    endpoint: "https://example.test/api/submissions",
    payload: payload("A"),
  });
  assert.strictEqual(resultA.submission_id, formA[1].payload.submission_id);
  assert.strictEqual(stored.size, 1, "Submitting A must leave B pending");

  const resultB = await window.PHONOSSubmission.submit({
    endpoint: "https://example.test/api/submissions",
    payload: payload("B"),
  });
  assert.strictEqual(resultB.submission_id, formB[1].payload.submission_id);
  assert.strictEqual(stored.size, 0);
  assert.notStrictEqual(resultA.submission_id, resultB.submission_id);

  const secondRunA = await window.PHONOSSubmission.submit({
    endpoint: "https://example.test/api/submissions",
    payload: payload("A"),
  });
  assert.notStrictEqual(
    secondRunA.submission_id,
    resultA.submission_id,
    "A new run of the same form must receive a new submission ID",
  );
  assert.strictEqual(stored.size, 0);

  console.log("Form isolation passed: forms are independent and each completed run resets its submission ID");
}

main().catch(error => {
  console.error(error);
  process.exit(1);
});
