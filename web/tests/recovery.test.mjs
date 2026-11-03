import assert from "node:assert/strict";
import { createServer as createHttpServer } from "node:http";
import { after, before, test } from "node:test";
import { fileURLToPath } from "node:url";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

let server;
let SamplePreviewFallback;
let Intake;

before(async () => {
  server = await createServer({
    root: fileURLToPath(new URL("..", import.meta.url)),
    configFile: false,
    // Attach HMR to an unbound server so rendering never opens a network port.
    server: {
      middlewareMode: true,
      hmr: { server: createHttpServer() },
      watch: null,
    },
    optimizeDeps: { noDiscovery: true },
    esbuild: { jsx: "automatic" },
    appType: "custom",
  });
  SamplePreviewFallback = (
    await server.ssrLoadModule("/src/SamplePreviewFallback.tsx")
  ).default;
  Intake = (await server.ssrLoadModule("/src/Intake.tsx")).default;
});

after(async () => {
  await server?.close();
});

test("live recovery links directly to credential-free samples in a separate tab", () => {
  const html = renderToStaticMarkup(
    createElement(SamplePreviewFallback, { publicPreview: false }),
  );
  const href = html.match(/href="([^"]+)"/)?.[1];
  assert.equal(
    href,
    "https://yashmodi1804.github.io/folio-invoice-verification/",
  );
  assert.equal(new URL(href).search, "");
  assert.equal(new URL(href).hash, "");
  assert.match(html, /target="_blank"/);
  assert.match(html, /rel="noopener noreferrer"/);
  assert.match(html, /Synthetic examples\. No uploads or server storage/);
});

test("the static preview does not offer a recovery link back to itself", () => {
  assert.equal(
    renderToStaticMarkup(
      createElement(SamplePreviewFallback, { publicPreview: true }),
    ),
    "",
  );
});

test("guest samples disclose preserved decisions without changing operator or preview labels", () => {
  const props = {
    token: "test-only",
    onCreated() {},
    onError() {},
    provider: "fixture",
    fallback: false,
    maxPages: 3,
    maxFileMb: 5,
    publicPreview: false,
    guest: true,
  };
  const guest = renderToStaticMarkup(createElement(Intake, props));
  assert.equal((guest.match(/aria-label="Open sample:/g) ?? []).length, 4);
  assert.match(guest, /Your saved reviews stay with each sample/);
  for (const publicPreview of [false, true]) {
    const html = renderToStaticMarkup(
      createElement(Intake, { ...props, guest: false, publicPreview }),
    );
    assert.doesNotMatch(
      html,
      /Your saved reviews stay|aria-label="Open sample:/,
    );
    assert.match(html, /Synthetic fixtures/);
  }
});
