/** Capture repeatable Folio UI frames for the narrated agency demo. */
import { createRequire } from "node:module";
import { mkdir } from "node:fs/promises";
import path from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const root = path.resolve(import.meta.dirname, "..");
const stills = path.join(root, "output", "video", "stills");
const token = process.env.FOLIO_DEMO_TOKEN ?? "local-demo-only";

async function capture(page, name) {
  await page.screenshot({ path: path.join(stills, `${name}.png`) });
  console.log(`Captured ${name}`);
}

async function scrollTo(page, heading) {
  const target = page.getByRole("heading", { name: heading, exact: true });
  await target.evaluate((element) => {
    element.scrollIntoView({ behavior: "instant", block: "center" });
  });
  await page.waitForTimeout(300);
}

await mkdir(stills, { recursive: true });
const browser = await chromium.launch({
  headless: true,
  executablePath:
    process.env.CHROME_PATH ??
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
});

try {
  const context = await browser.newContext({
    viewport: { width: 1600, height: 900 },
    deviceScaleFactor: 1.2,
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  await page.goto("http://127.0.0.1:8000/", { waitUntil: "networkidle" });
  await page.getByLabel("Operator access token").fill(token);
  await page.getByRole("button", { name: "Open workspace" }).click();
  await page.getByRole("textbox", { name: "Search documents" }).fill("deltaforge");
  await page.getByRole("button", { name: /Open 04-deltaforge-complex-challenge\.pdf/ }).first().click();
  await page.getByRole("heading", { name: "DELTAFORGE" }).waitFor();
  await page.getByAltText("Original invoice, page 1").waitFor();
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
  await page.waitForTimeout(300);

  await capture(page, "01-source");

  await page.getByRole("button", { name: "Next page" }).click();
  await page.getByRole("button", { name: "Next page" }).click();
  await page.getByAltText("Original invoice, page 3").waitFor();
  await page.evaluate(() => window.scrollTo({ top: 300, behavior: "instant" }));
  await capture(page, "02-final-page");

  await scrollTo(page, "Audit trail");
  await capture(page, "03-audit");

  await scrollTo(page, "Verification ledger");
  await capture(page, "04-ledger");

  await scrollTo(page, "Your decision, on record");
  await capture(page, "05-review");

  await scrollTo(page, "Processing trace");
  await page.evaluate(() => window.scrollBy({ top: 180, behavior: "instant" }));
  await capture(page, "06-trace");

  await context.close();
} finally {
  await browser.close();
}
