/** Capture the real, saved Folio workflow without requesting model inference. */
import { createRequire } from "node:module";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const root = path.resolve(import.meta.dirname, "..");
const media = path.join(root, "output", "video", "folio-60s");
const stills = path.join(media, "stills");
const token = process.env.FOLIO_DEMO_TOKEN ?? "local-demo-only";
const base = process.env.FOLIO_DEMO_URL ?? "http://127.0.0.1:8000";
const challengeId = "072a609f-1806-4733-bab2-a365e65ad85c";
const reviewedId = "34819219-f081-42f3-9d4d-692b50362c7e";
const approvedId = "2f64f16e-f0ef-4fb0-bbe4-32754d4159d4";

async function screenshot(page, name) {
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(200);
  await page.screenshot({ path: path.join(stills, `${name}.png`) });
  console.log(`Captured ${name}`);
}

async function openJob(page, filename, position = 0) {
  const back = page.getByRole("button", { name: "All documents" });
  if (await back.isVisible()) await back.click();
  await page.getByRole("textbox", { name: "Search documents" }).fill(filename);
  await page.getByRole("button", { name: `Open ${filename}`, exact: true }).nth(position).click();
  await page.getByAltText("Original invoice, page 1").waitFor();
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
}

async function focus(page, heading, offset = 0) {
  await page.getByRole("heading", { name: heading, exact: true }).evaluate((element) => {
    element.scrollIntoView({ behavior: "instant", block: "center" });
  });
  if (offset) await page.evaluate((pixels) => window.scrollBy(0, pixels), offset);
}

async function api(page, route) {
  const response = await page.request.get(`${base}/api/v1${route}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok()) throw new Error(`${route}: HTTP ${response.status()}`);
  return response.json();
}

await mkdir(stills, { recursive: true });
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
});

try {
  const context = await browser.newContext({
    viewport: { width: 1600, height: 900 },
    deviceScaleFactor: 1.2,
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  await page.goto(base, { waitUntil: "networkidle" });
  await page.getByLabel("Operator access token").fill(token);
  await page.getByRole("button", { name: "Open workspace" }).click();
  await page.getByRole("heading", { name: "From paperwork to proof." }).waitFor();
  await focus(page, "A document in. A decision out.");
  await screenshot(page, "01-intake");

  await openJob(page, "04-deltaforge-complex-challenge.pdf");
  await page.getByRole("heading", { name: "DELTAFORGE" }).waitFor();
  await screenshot(page, "02-source");
  await page.getByRole("button", { name: "Next page" }).click();
  await page.getByRole("button", { name: "Next page" }).click();
  await page.getByAltText("Original invoice, page 3").waitFor();
  await page.evaluate(() => window.scrollTo({ top: 280, behavior: "instant" }));
  await screenshot(page, "03-fields");
  await focus(page, "Processing trace", 460);
  await screenshot(page, "04-trace");
  await focus(page, "Verification ledger", 700);
  await screenshot(page, "05-ledger");
  await focus(page, "Your decision, on record");
  await screenshot(page, "06-review");

  const meridianJobs = (await api(page, "/jobs")).filter((job) => job.filename === "03-meridian-missing-date.pdf");
  const reviewedPosition = meridianJobs.findIndex((job) => job.job_id === reviewedId);
  if (reviewedPosition < 0) throw new Error("Reviewed example is not in the document register");
  await openJob(page, "03-meridian-missing-date.pdf", reviewedPosition);
  await page.getByRole("heading", { name: "Review decision" }).waitFor();
  await focus(page, "Audit trail", 250);
  await screenshot(page, "07-audit");

  await openJob(page, "northline-clean.pdf");
  await page.getByRole("heading", { name: "Northline Studio" }).waitFor();
  await screenshot(page, "08-approved");

  const challenge = await api(page, `/jobs/${challengeId}`);
  const reviewed = await api(page, `/jobs/${reviewedId}`);
  const approved = await api(page, `/jobs/${approvedId}`);
  const erp = await api(page, `/jobs/${approvedId}/erp-export`);
  if (challenge.status !== "REQUIRES_HUMAN_REVIEW") throw new Error("Challenge state changed");
  if (reviewed.status !== "HUMAN_APPROVED") throw new Error("Reviewed record state changed");
  const reviewAudit = await api(page, `/jobs/${reviewedId}/audit`);
  if (!reviewAudit.some((event) => event.event === "HUMAN_APPROVED" && event.details?.changes?.invoice_date)) {
    throw new Error("Reviewed example has no dated correction");
  }
  if (approved.status !== "AUTO_APPROVED") throw new Error("Fixture state changed");
  if (erp.schema_version !== "folio.erp-export.v1") throw new Error("Export contract changed");
  const totalCheck = challenge.result.checks.find((check) => check.code === "TOTAL");
  if (totalCheck?.state !== "FAIL" || totalCheck.variance !== "50.00") {
    throw new Error("Challenge total variance changed");
  }
  await writeFile(
    path.join(media, "manifest.json"),
    JSON.stringify({
      challenge: {
        id: challengeId,
        provider: challenge.result.telemetry.provider,
        model: challenge.result.telemetry.model,
        input_tokens: challenge.result.telemetry.input_tokens,
        output_tokens: challenge.result.telemetry.output_tokens,
        page_plan: challenge.result.telemetry.page_plan,
        total_check: totalCheck,
        route_reasons: challenge.result.route_reasons,
      },
      reviewed: { id: reviewedId, status: reviewed.status },
      approved: { id: approvedId, status: approved.status, export: erp },
    }, null, 2),
  );
  await context.close();
} finally {
  await browser.close();
}
