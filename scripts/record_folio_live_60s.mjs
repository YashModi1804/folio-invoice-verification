/** Record one continuous operator walkthrough of the real Folio UI. */
import { createRequire } from "node:module";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const root = path.resolve(import.meta.dirname, "..");
const media = path.join(root, "output", "video", "folio-live-60s");
const base = process.env.FOLIO_DEMO_URL ?? "http://127.0.0.1:8000";
const token = process.env.FOLIO_DEMO_TOKEN ?? "local-demo-only";
const correctedId = "34819219-f081-42f3-9d4d-692b50362c7e";
const approvedId = "2f64f16e-f0ef-4fb0-bbe4-32754d4159d4";
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function smoothFocus(page, heading, extra = 0) {
  await page.getByRole("heading", { name: heading, exact: true }).evaluate((element) => {
    element.scrollIntoView({ behavior: "smooth", block: "center" });
  });
  if (extra) await page.evaluate((pixels) => window.scrollBy({ top: pixels, behavior: "smooth" }), extra);
  await wait(600);
}

async function badge(page, text) {
  await page.evaluate((value) => {
    let element = document.getElementById("folio-film-badge");
    if (!element) {
      element = document.createElement("div");
      element.id = "folio-film-badge";
      Object.assign(element.style, {
        position: "fixed", top: "22px", right: "100px", zIndex: "2147483645",
        background: "#153236", color: "#f6f5eb", border: "1px solid #67887e",
        borderRadius: "7px", padding: "11px 16px", font: "700 13px Arial",
        letterSpacing: "1.5px", pointerEvents: "none", boxShadow: "0 8px 25px #091f2180",
      });
      document.body.append(element);
    }
    element.textContent = value;
  }, text);
}

async function moveTo(page, locator) {
  const box = await locator.boundingBox();
  if (!box) throw new Error("Target is not visible during recording");
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 18 });
}

async function openSaved(page, filename, position) {
  const back = page.getByRole("button", { name: "All documents" });
  if (await back.isVisible()) {
    await moveTo(page, back);
    await back.click();
  }
  const search = page.getByRole("textbox", { name: "Search documents" });
  await search.fill(filename);
  const button = page.getByRole("button", { name: `Open ${filename}`, exact: true }).nth(position);
  await moveTo(page, button);
  await button.click();
  await page.getByAltText("Original invoice, page 1").waitFor();
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
}

await mkdir(media, { recursive: true });
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
});
const context = await browser.newContext({
  viewport: { width: 1920, height: 1080 },
  deviceScaleFactor: 1,
  reducedMotion: "reduce",
  recordVideo: { dir: media, size: { width: 1920, height: 1080 } },
  extraHTTPHeaders: { Authorization: `Bearer ${token}` },
});
await context.addInitScript((value) => {
  sessionStorage.setItem("folio-token", value);
  const setup = () => {
    const cursor = document.createElement("div");
    cursor.id = "folio-film-cursor";
    Object.assign(cursor.style, {
      position: "fixed", left: "-50px", top: "-50px", width: "30px", height: "30px",
      border: "2px solid #d5a260", borderRadius: "50%", background: "#d5a26033",
      transform: "translate(-50%, -50%)", pointerEvents: "none", zIndex: "2147483646",
      boxShadow: "0 0 0 3px #17323677", transition: "left 35ms linear, top 35ms linear",
    });
    document.body.append(cursor);
    document.addEventListener("mousemove", (event) => {
      cursor.style.left = `${event.clientX}px`;
      cursor.style.top = `${event.clientY}px`;
    });
    document.addEventListener("mousedown", () => {
      cursor.style.background = "#d5a26099";
      cursor.style.boxShadow = "0 0 0 15px #d5a26055";
      setTimeout(() => {
        cursor.style.background = "#d5a26033";
        cursor.style.boxShadow = "0 0 0 3px #17323677";
      }, 350);
    });
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", setup, { once: true });
  else setup();
}, token);

const pageCreatedAt = Date.now();
const page = await context.newPage();
let rawPath;
let startOffsetSec;
try {
  await page.goto(base, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: "From paperwork to proof." }).waitFor();
  await page.evaluate(() => document.fonts.ready);
  const jobsResponse = await page.request.get(`${base}/api/v1/jobs`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!jobsResponse.ok()) throw new Error(`Jobs endpoint: ${jobsResponse.status()}`);
  const savedJobs = await jobsResponse.json();
  const positionOf = (filename, id) => savedJobs
    .filter((job) => job.filename === filename)
    .findIndex((job) => job.job_id === id);
  const correctedPosition = positionOf("03-meridian-missing-date.pdf", correctedId);
  const approvedPosition = positionOf("northline-clean.pdf", approvedId);
  if (correctedPosition < 0 || approvedPosition < 0) throw new Error("Required saved demo job is missing");
  await badge(page, "LIVE WALKTHROUGH · SAVED SYNTHETIC RUNS");
  await page.mouse.move(1740, 930);
  const started = Date.now();
  startOffsetSec = (started - pageCreatedAt) / 1000;
  const at = async (seconds, action) => {
    await wait(Math.max(0, started + seconds * 1000 - Date.now()));
    await action();
    console.log(`${seconds}s · ${action.name || "step"}`);
  };

  await at(1, async () => {
    const button = page.getByRole("button", { name: "New document" });
    await moveTo(page, button);
    await button.click();
  });
  await at(4, async () => {
    await moveTo(page, page.getByRole("button", { name: "Choose a document" }));
  });
  await at(7, async () => {
    await smoothFocus(page, "Document register");
    const search = page.getByRole("textbox", { name: "Search documents" });
    await moveTo(page, search);
    await search.click();
    await search.pressSequentially("deltaforge", { delay: 75 });
  });
  await at(11, async () => {
    const button = page.getByRole("button", { name: "Open 04-deltaforge-complex-challenge.pdf" }).first();
    await moveTo(page, button);
    await button.click();
    await page.getByRole("heading", { name: "DELTAFORGE" }).waitFor();
    await page.getByAltText("Original invoice, page 1").waitFor();
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
    await badge(page, "RECORDED GROQ · SYNTHETIC INVOICE");
  });
  await at(17, async () => {
    const evidence = page.getByRole("button", { name: "View Invoice Number source evidence" });
    await moveTo(page, evidence);
    await evidence.click();
  });
  await at(21, async () => {
    const next = page.getByRole("button", { name: "Next page" });
    await moveTo(page, next);
    await next.click();
    await wait(450);
    await next.click();
    await page.getByAltText("Original invoice, page 3").waitFor();
  });
  await at(24, async () => {
    await page.mouse.wheel(0, 370);
  });
  await at(27, async () => {
    await smoothFocus(page, "Verification ledger");
  });
  await at(31, async () => {
    await page.mouse.wheel(0, 520);
  });
  await at(34, async () => {
    await page.mouse.wheel(0, 430);
  });
  await at(39, async () => {
    await smoothFocus(page, "Your decision, on record");
    const note = page.getByRole("textbox", { name: "Review note · required" });
    await moveTo(page, note);
    await note.click();
    await note.pressSequentially("Check $50 and page 2.", { delay: 35 });
  });
  await at(42, async () => {
    await openSaved(page, "03-meridian-missing-date.pdf", correctedPosition);
    await badge(page, "SEPARATE REVIEWED LOCAL DEMO · SYNTHETIC");
    await page.getByRole("heading", { name: "Audit trail", exact: true }).evaluate((element) => {
      element.scrollIntoView({ behavior: "instant", block: "start" });
    });
    await page.mouse.wheel(0, 180);
  });
  await at(51, async () => {
    await openSaved(page, "northline-clean.pdf", approvedPosition);
    await badge(page, "SEPARATE APPROVED FIXTURE · SYNTHETIC");
  });
  await at(55, async () => {
    const response = await page.request.get(`${base}/api/v1/jobs/${approvedId}/erp-export`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok()) throw new Error(`ERP export: ${response.status()}`);
    const exportData = await response.json();
    if (exportData.schema_version !== "folio.erp-export.v1") throw new Error("ERP export contract changed");
    const formatted = JSON.stringify(exportData, null, 2);
    await page.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>
      body{margin:0;background:#142e31;color:#f6f4ea;font-family:Arial,sans-serif}
      header{padding:30px 58px;border-bottom:1px solid #577572;display:flex;justify-content:space-between;align-items:center}
      header strong{font-size:25px}header span{font-size:17px;color:#b8d5c7;letter-spacing:1px}
      main{display:grid;grid-template-columns:40% 60%;gap:35px;padding:75px 58px}
      h1{font:400 76px/1.05 Georgia,serif;margin:0 0 35px}
      p{font-size:28px;line-height:1.4;color:#d2e3d9;max-width:640px}
      .pill{display:inline-block;margin-top:42px;padding:16px 22px;border:1px solid #90caa3;color:#b4ebc4;font-weight:700;font-size:20px}
      pre{margin:0;background:#f6f4ea;color:#173236;padding:30px 38px;font:19px/1.45 Menlo,monospace;height:780px;overflow:auto;white-space:pre-wrap;word-break:break-word}
      small{display:block;margin-top:35px;color:#b5ccbf;font-size:17px}
    </style></head><body><header><strong>f / folio</strong><span>LIVE LOCAL API RESPONSE · FORMATTED FOR VIEWING</span></header>
      <main><section><h1>Approved.<br>Ready to integrate.</h1>
        <p>Only approved records expose this versioned, idempotent ERP export. A client connector controls the destination write.</p>
        <div class="pill">GET /api/v1/jobs/{id}/erp-export · 200 OK</div>
        <small>Separate synthetic fixture · no outbound ERP write</small>
      </section><pre>${formatted.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")}</pre></main>
    </body></html>`);
    await page.mouse.move(1750, 770, { steps: 18 });
    await page.mouse.wheel(0, 230);
  });
  await wait(Math.max(0, started + 60_150 - Date.now()));
  rawPath = await page.video().path();
  await writeFile(path.join(media, "recording.json"), JSON.stringify({
    rawPath, startOffsetSec, durationSec: 60, recordedAt: new Date().toISOString(),
    source: "Continuous Playwright browser recording of live UI interactions; saved results, no inference call",
  }, null, 2));
} finally {
  await context.close();
  await browser.close();
}
console.log(`Raw recording: ${rawPath}`);
console.log(`Trim start: ${startOffsetSec.toFixed(3)}s`);
