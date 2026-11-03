import test from "node:test";
import assert from "node:assert/strict";
import { ApiError, parserErrorMessage, requestJson } from "../src/http.ts";

test("API requests preserve authorization, cancellation and JSON content type", async (t) => {
  const controller = new AbortController();
  t.mock.method(globalThis, "fetch", async (url, options) => {
    assert.equal(url, "/api/v1/review");
    assert.equal(options.headers.get("Authorization"), "Bearer test-token");
    assert.equal(options.headers.get("Content-Type"), "application/json");
    assert.equal(options.signal.aborted, false);
    return Response.json({ saved: true });
  });
  const result = await requestJson("/api/v1/review", "test-token", {
    method: "POST",
    body: "{}",
    signal: controller.signal,
  });
  assert.deepEqual(result, { saved: true });
});

test("multipart boundary remains controlled by the browser", async (t) => {
  t.mock.method(globalThis, "fetch", async (_url, options) => {
    assert.equal(options.headers.has("Content-Type"), false);
    return Response.json({ job_id: "one" }, { status: 202 });
  });
  await requestJson("/api/v1/documents", "", {
    method: "POST",
    body: new FormData(),
  });
});

test("field validation errors tell the reviewer which correction needs attention", async (t) => {
  t.mock.method(globalThis, "fetch", async () =>
    Response.json(
      {
        detail: [
          {
            loc: ["body", "corrected_invoice", "invoice_date", "value"],
            msg: "Input should be a valid date",
          },
        ],
      },
      { status: 422 },
    ),
  );
  await assert.rejects(requestJson("/api/v1/review", ""), (error) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.status, 422);
    assert.equal(error.message, "invoice date: Input should be a valid date");
    return true;
  });
});

test("a hosting wake page produces a useful retry message", async (t) => {
  t.mock.method(
    globalThis,
    "fetch",
    async () =>
      new Response("<html>Starting</html>", {
        headers: { "Content-Type": "text/html" },
      }),
  );
  await assert.rejects(
    requestJson("/api/v1/jobs", ""),
    (error) => error.status === 503 && /starting/.test(error.message),
  );
});

test("a server error does not expose its HTML body", async (t) => {
  t.mock.method(
    globalThis,
    "fetch",
    async () => new Response("private stack trace", { status: 500 }),
  );
  await assert.rejects(
    requestJson("/api/v1/jobs", ""),
    (error) => error.status === 500 && !error.message.includes("stack trace"),
  );
});

test("safe parser failures explain the next step for upload and source preview", async (t) => {
  let code = "PARSER_BUSY";
  t.mock.method(globalThis, "fetch", async () =>
    Response.json(
      { detail: code },
      { status: code === "PARSER_BUSY" ? 503 : 422 },
    ),
  );
  for (const parserCode of [
    "PARSER_BUSY",
    "PARSER_TIMEOUT",
    "PARSER_RESOURCE_LIMIT",
    "PARSER_OUTPUT_LIMIT",
    "PARSER_FAILED",
  ]) {
    code = parserCode;
    await assert.rejects(requestJson("/api/v1/documents", ""), (error) => {
      assert.ok(error instanceof ApiError);
      assert.equal(error.message, parserErrorMessage(code));
      assert.match(error.message, /try/i);
      assert.ok(!error.message.includes("PARSER_"));
      return true;
    });
  }
  assert.equal(parserErrorMessage("UNRECOGNIZED"), null);
});

test("network failures are recoverable and write requests are not automatically replayed", async (t) => {
  const mocked = t.mock.method(globalThis, "fetch", async () => {
    throw new TypeError("Failed to fetch");
  });
  await assert.rejects(
    requestJson("/api/v1/documents", "", {
      method: "POST",
      body: new FormData(),
    }),
    /Check your connection/,
  );
  assert.equal(mocked.mock.callCount(), 1);
});
