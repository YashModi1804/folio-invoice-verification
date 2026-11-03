import test from "node:test";
import assert from "node:assert/strict";
import {
  RequestScope,
  fieldWasCorrected,
  matchesDocument,
  prioritizeReviews,
  validEvidence,
} from "../src/workspace.ts";

const job = (id, created_at, failed = 0) => ({
  job_id: id,
  filename: "invoice.pdf",
  summary: { vendor_name: "Northline", invoice_number: "NS-2026-041" },
  created_at,
  status: "REQUIRES_HUMAN_REVIEW",
  result: { checks: Array.from({ length: failed }, () => ({ state: "FAIL" })) },
});

test("a corrected value is marked reviewed even when original model confidence is retained", () => {
  const original = {
    value: "1300.00",
    confidence: 0.95,
    evidence: [{ page_number: 2, text: "Total 1300.00" }],
  };
  const reviewed = { ...original, value: "1250.00" };
  assert.equal(fieldWasCorrected(original, reviewed), true);
  assert.equal(fieldWasCorrected(original, { ...original }), false);
  assert.equal(fieldWasCorrected({ ...original, value: null }, reviewed), true);
  assert.equal(original.value, "1300.00");
});

test("a slow poll cannot overlap or replace a newer requested refresh", () => {
  const scope = new RequestScope();
  const poll = scope.start();
  assert.equal(scope.start(), null);
  const refresh = scope.start(true);
  assert.equal(poll.signal.aborted, true);
  assert.equal(scope.owns(poll), false);
  scope.finish(poll);
  assert.equal(scope.owns(refresh), true);
  scope.finish(refresh);
  assert.ok(scope.start());
});

test("signing out invalidates a response from the previous workspace", async () => {
  const scope = new RequestScope();
  const oldRequest = scope.start();
  let resolve;
  const response = new Promise((done) => {
    resolve = done;
  });
  const visible = [];
  const load = response.then((items) => {
    if (scope.owns(oldRequest)) visible.push(...items);
  });
  scope.cancel();
  const guestRequest = scope.start();
  resolve(["private operator invoice"]);
  await load;
  assert.deepEqual(visible, []);
  assert.equal(scope.owns(guestRequest), true);
});

test("document search includes invoice number and trims whitespace", () => {
  const item = job("one", "2026-01-01");
  assert.equal(matchesDocument(item, "  ns-2026-041  "), true);
  assert.equal(matchesDocument(item, "NORTHLINE"), true);
  assert.equal(matchesDocument(item, "invoice.pdf"), true);
  assert.equal(matchesDocument(item, "missing"), false);
});

test("evidence cannot send a reviewer outside the source document", () => {
  const evidence = [
    { page_number: 99, text: "invalid" },
    { page_number: 2, text: "valid" },
  ];
  assert.deepEqual(validEvidence({ evidence }, 2), evidence[1]);
  assert.equal(
    validEvidence({ evidence: [{ page_number: 0, text: "invalid" }] }, 2),
    undefined,
  );
  assert.equal(validEvidence({ evidence: [] }, 2), undefined);
});

test("review prioritization uses discrepancies then oldest receipt without changing the register", () => {
  const jobs = [
    job("new", "2026-01-03", 0),
    job("old", "2026-01-01", 0),
    job("severe", "2026-01-02", 2),
  ];
  jobs.push({ ...job("approved", "2025-01-01", 3), status: "AUTO_APPROVED" });
  assert.deepEqual(
    prioritizeReviews(jobs).map((item) => item.job_id),
    ["severe", "old", "new"],
  );
  assert.deepEqual(
    jobs.map((item) => item.job_id),
    ["new", "old", "severe", "approved"],
  );
});
