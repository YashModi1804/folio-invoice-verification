import assert from "node:assert/strict";
import test from "node:test";
import {
  LIVE_ORIGIN,
  probeWorkspace,
  waitForWorkspace,
} from "../public/launch/readiness.js";

test("launch probe requires the Folio readiness contract and omits credentials", async () => {
  const ready = await probeWorkspace(async (url, options) => {
    assert.equal(url, `${LIVE_ORIGIN}/health/launch`);
    assert.equal(options.credentials, "omit");
    assert.equal(options.redirect, "error");
    return Response.json({ status: "ready" });
  });
  assert.equal(ready, true);
  for (const response of [
    new Response("Render is starting"),
    Response.json({ status: "starting" }),
    Response.json({ status: "ready" }, { status: 503 }),
  ]) {
    assert.equal(await probeWorkspace(async () => response), false);
  }
});

test("a cold-start/CORS failure is retried until readiness succeeds", async () => {
  let calls = 0;
  let time = 0;
  assert.equal(
    await waitForWorkspace({
      probe: async () => {
        if (++calls === 1) throw new TypeError("Failed to fetch");
        return calls === 3;
      },
      clock: () => time,
      pause: async (ms) => {
        time += ms;
      },
    }),
    true,
  );
  assert.equal(calls, 3);
});

test("an unavailable backend reaches a bounded timeout", async () => {
  let calls = 0;
  let time = 0;
  assert.equal(
    await waitForWorkspace({
      timeoutMs: 6_000,
      probe: async () => {
        calls++;
        return false;
      },
      clock: () => time,
      pause: async (ms) => {
        time += ms;
      },
    }),
    false,
  );
  assert.equal(calls, 2);
});

test("leaving the page cancels startup and prevents a late redirect", async () => {
  const controller = new AbortController();
  assert.equal(
    await waitForWorkspace({
      signal: controller.signal,
      probe: async () => {
        controller.abort();
        return true;
      },
    }),
    false,
  );
});
