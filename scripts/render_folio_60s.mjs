/** Render the approved 60-second Folio story using local voice and captured UI. */
import { createRequire } from "node:module";
import { execFileSync } from "node:child_process";
import { mkdir, readFile } from "node:fs/promises";
import path from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const root = path.resolve(import.meta.dirname, "..");
const media = path.join(root, "output", "video", "folio-60s");
const frames = path.join(media, "frames");
const ffmpeg = process.env.FFMPEG_PATH ?? "/opt/homebrew/bin/ffmpeg";
const ffprobe = process.env.FFPROBE_PATH ?? "/opt/homebrew/bin/ffprobe";
const output = path.join(root, "output", "video", "folio-60s-agency-demo.mp4");
const manifest = JSON.parse(await readFile(path.join(media, "manifest.json"), "utf8"));

const narration = [
  "For client invoices, extraction is only the start. Folio shows when the data should not be trusted.",
  "Each upload becomes a durable job. The worker inspects the PDF, selects pages within provider limits, and records its plan.",
  "This recorded Groq run shows typed fields beside the synthetic source, with page references and actual token usage.",
  "Python checks captured lines and totals with decimal arithmetic. A skipped page stays incomplete, and a fifty-dollar variance blocks approval.",
  "The exception enters human review. Corrections are appended; the original extraction, verification ledger, and audit history remain available.",
  "FastAPI and durable workers make Folio reusable. Only approved records reach its versioned, idempotent ERP export.",
];

const scenes = [
  { at: 0, length: 7, image: "01-intake.png", chapter: "01 / INTAKE", title: "A document in. A decision out.", subtitle: "An invoice enters an auditable workflow.", voice: 0, provenance: "SYNTHETIC DEMO · LOCAL WORKSPACE" },
  { at: 7, length: 10, image: "02-source.png", chapter: "02 / DURABLE JOB", title: "The source remains visible.", subtitle: "Upload → persisted job → page planning → extraction", voice: 1, provenance: "RECORDED GROQ · SYNTHETIC SOURCE" },
  { at: 17, length: 5, image: "03-fields.png", chapter: "03 / TYPED EXTRACTION", title: "Fields beside the source.", subtitle: "Model output is schema-validated before use.", voice: 2, provenance: "RECORDED GROQ · SYNTHETIC SOURCE" },
  { at: 22, length: 5, image: "04-trace.png", chapter: "04 / PROVIDER TRACE", title: "The run leaves a trace.", subtitle: `${manifest.challenge.input_tokens.toLocaleString()} input · ${manifest.challenge.output_tokens.toLocaleString()} output tokens · pages 1, 3 selected`, voice: null, provenance: "RECORDED GROQ · SYNTHETIC SOURCE" },
  { at: 27, length: 12, image: "05-ledger.png", chapter: "05 / INDEPENDENT VERIFICATION", title: "The model does not approve itself.", subtitle: "Page 2 skipped · Printed 8,890.66 · Calculated 8,840.66 · Δ 50.00", voice: 3, provenance: "RECORDED GROQ · SYNTHETIC SOURCE" },
  { at: 39, length: 6, image: "06-review.png", chapter: "06 / HUMAN REVIEW", title: "Automation stops safely.", subtitle: "The exception is held until a reviewer decides.", voice: 4, provenance: "RECORDED GROQ · SYNTHETIC SOURCE" },
  { at: 45, length: 5, image: "07-audit.png", chapter: "07 / AUDIT TRAIL", title: "Corrections leave a trail.", subtitle: "Reviewer-supplied date · original extraction retained", voice: null, provenance: "SEPARATE REVIEWED LOCAL DEMO" },
  { at: 50, length: 5, special: "architecture", chapter: "08 / REUSABLE ARCHITECTURE", voice: 5, provenance: "FOLIO / ENGINEERING VIEW" },
  { at: 55, length: 5, special: "export", chapter: "09 / ERP HANDOFF", voice: null, provenance: "SEPARATE APPROVED FIXTURE" },
];

const esc = (value) => String(value).replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
const imageData = async (name) => `data:image/png;base64,${(await readFile(path.join(media, "stills", name))).toString("base64")}`;

function commonCss() {
  return `
    * { box-sizing: border-box; }
    html, body { width: 1920px; height: 1080px; margin: 0; overflow: hidden; }
    body { font-family: Arial, Helvetica, sans-serif; background: #142d30; color: #f7f6ed; }
    .stage { position: relative; width: 1920px; height: 1080px; overflow: hidden; }
    .screen { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
    .shade { position: absolute; bottom: 0; left: 0; right: 0; height: 240px;
      background: linear-gradient(transparent, rgba(10,31,33,.6) 26%, rgba(10,31,33,.97) 70%); }
    .chapter { position: absolute; top: 35px; left: 38px; padding: 13px 19px; border-radius: 7px;
      background: #173236; color: #bce0d0; font-size: 18px; font-weight: 700; letter-spacing: 2px; }
    .provenance { position: absolute; top: 35px; right: 38px; padding: 13px 19px;
      background: #173236; border: 1px solid #66867a; border-radius: 7px;
      font-size: 18px; letter-spacing: 1.2px; font-weight: 700; }
    .caption { position: absolute; left: 72px; bottom: 58px; width: 1700px; }
    .caption h1 { font-family: Georgia, serif; font-weight: 400; font-size: 63px; line-height: 1;
      margin: 0 0 18px; }
    .caption p { font-size: 25px; color: #cee0d7; margin: 0; }
    .mark { position: absolute; right: 62px; bottom: 57px; font-family: Georgia, serif;
      font-size: 28px; color: #d8a35a; }
    .rail { position: absolute; left: 0; right: 0; bottom: 0; height: 8px; background: #355458; }
    .rail span { display: block; height: 8px; background: #d8a35a; }
  `;
}

function screenshotHtml(scene, image) {
  return `<img class="screen" src="${image}"><div class="shade"></div>
    <div class="caption"><h1>${esc(scene.title)}</h1><p>${esc(scene.subtitle)}</p></div>`;
}

function architectureHtml() {
  const nodes = [
    ["01", "FASTAPI", "Auth · intake · idempotency"],
    ["02", "DURABLE WORKER", "Database-backed jobs"],
    ["03", "PROVIDER ADAPTER", "Groq · Gemini · local"],
    ["04", "PYDANTIC + DECIMAL", "Typed fields · independent checks"],
    ["05", "ROUTING POLICY", "Review or approved"],
  ];
  return `<div class="architecture">
      <div class="arch-kicker">ENGINEERING / THE CONTROL PATH</div>
      <h1>Reliable AI is an architecture.</h1>
      <div class="nodes">${nodes.map(([number, title, detail], index) => `
        <div class="node"><small>${number}</small><strong>${title}</strong><span>${detail}</span></div>
        ${index < nodes.length - 1 ? '<div class="arrow">→</div>' : ""}`).join("")}</div>
      <div class="arch-foot">A model proposes. Deterministic code verifies. Policy decides. A human can intervene.</div>
    </div><style>
      .architecture { padding: 175px 105px 0; height: 100%; background: radial-gradient(circle at 95% 0%, #25464a, #132d30 58%); }
      .arch-kicker { font-size: 22px; letter-spacing: 4px; color: #b7d2c6; font-weight: 700; }
      .architecture h1 { font: 400 84px Georgia,serif; margin: 35px 0 95px; }
      .nodes { display: flex; align-items: stretch; gap: 14px; }
      .node { width: 280px; min-height: 245px; padding: 30px 25px; background: #f7f5eb; color: #153236; border-top: 7px solid #d6a25b; }
      .node small { display: block; font-size: 20px; color: #a56c2d; margin-bottom: 25px; }
      .node strong { display: block; font-size: 28px; line-height: 1.14; min-height: 62px; }
      .node span { display: block; margin-top: 20px; font-size: 20px; line-height: 1.25; color: #587070; }
      .arrow { align-self: center; font-size: 36px; color: #d6a25b; }
      .arch-foot { margin-top: 75px; padding-top: 28px; border-top: 1px solid #527073; font-size: 30px; color: #d2e1d9; }
    </style>`;
}

function exportHtml() {
  const contract = manifest.approved.export;
  const invoice = contract.invoice;
  return `<div class="export">
      <div class="export-left">
        <div class="export-kicker">APPROVED PATH / SEPARATE SYNTHETIC FIXTURE</div>
        <h1>Verified in.<br>ERP-ready out.</h1>
        <p>Only approved records expose this versioned handoff. A client connector controls the actual ERP write.</p>
        <div class="approved">✓ ${esc(contract.folio.status)} · ${esc(invoice.supplier.name)} · ${esc(invoice.amounts.total)} ${esc(invoice.currency)}</div>
      </div>
      <div class="export-card">
        <div class="card-head"><span>ERP export · selected response fields</span><span>200 OK</span></div>
        <div class="json">
          <div><em>schema_version</em> <b>${esc(contract.schema_version)}</b></div>
          <div><em>event_type</em> <b>${esc(contract.event_type)}</b></div>
          <div><em>idempotency_key</em> <b>folio:…:v1</b></div>
          <div><em>invoice.supplier.name</em> <b>${esc(invoice.supplier.name)}</b></div>
          <div><em>invoice.invoice_number</em> <b>${esc(invoice.invoice_number)}</b></div>
          <div><em>invoice.amounts.total</em> <b>${esc(invoice.amounts.total)} ${esc(invoice.currency)}</b></div>
          <div><em>verification.math_validated</em> <span class="green">true</span></div>
        </div>
        <div class="card-foot">Connector-ready JSON · No outbound ERP write by default</div>
      </div>
    </div><style>
      .export { display: flex; gap: 90px; padding: 180px 100px 0; width: 100%; height: 100%;
        background: radial-gradient(circle at 85% 8%, #305151, #142d30 60%); }
      .export-left { width: 770px; }
      .export-kicker { color: #b7d2c6; font-size: 20px; letter-spacing: 3px; font-weight: 700; }
      .export h1 { font: 400 91px/1.05 Georgia,serif; margin: 45px 0 38px; }
      .export p { font-size: 29px; color: #d0e0d9; line-height: 1.4; width: 680px; }
      .approved { margin-top: 72px; color: #b8e1c2; font-size: 25px; font-weight: 700; }
      .export-card { width: 860px; height: 640px; background: #f6f4ea; color: #173236;
        box-shadow: 0 25px 90px #081d1e; border-top: 9px solid #a2c8ac; }
      .card-head { display: flex; justify-content: space-between; padding: 26px 34px;
        border-bottom: 1px solid #d6e1da; font: 700 20px Arial,sans-serif; }
      .card-head span:last-child { color: #34744a; }
      .json { padding: 28px 40px; font: 23px/1.85 Menlo,monospace; white-space: nowrap; }
      .json em { color: #6b695d; font-style: normal; }
      .json b { color: #136b70; font-weight: 500; }
      .json .green { color: #27764b; font-weight: 700; }
      .card-foot { border-top: 1px solid #d6e1da; margin: 0 35px; padding-top: 19px;
        color: #596d6c; font-size: 20px; }
    </style>`;
}

await mkdir(frames, { recursive: true });
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.CHROME_PATH ?? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
});
try {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  for (const [index, scene] of scenes.entries()) {
    const body = scene.special === "architecture" ? architectureHtml()
      : scene.special === "export" ? exportHtml()
        : screenshotHtml(scene, await imageData(scene.image));
    await page.setContent(`<!doctype html><html><head><meta charset="utf-8"><style>${commonCss()}</style></head><body>
      <div class="stage">${body}<div class="chapter">${esc(scene.chapter)}</div>
      <div class="provenance">${esc(scene.provenance)}</div><div class="mark">f / folio</div>
      <div class="rail"><span style="width:${((scene.at + scene.length) / 60) * 100}%"></span></div></div>
      </body></html>`);
    if (scene.image) await page.locator(".screen").evaluate((element) => element.decode());
    await page.screenshot({ path: path.join(frames, `scene-${index + 1}.png`) });
    console.log(`Rendered scene ${index + 1}`);
  }
} finally {
  await browser.close();
}

const voiceStarts = [0.38, 7.38, 17.38, 27.38, 39.38, 50.38];
const voiceEnds = [7, 17, 27, 39, 50, 60];
for (const [index, line] of narration.entries()) {
  const voice = path.join(media, `voice-${index + 1}.aiff`);
  execFileSync("say", ["-v", "Daniel", "-r", "175", "-o", voice, line]);
  const duration = Number(execFileSync(ffprobe, [
    "-v", "error", "-show_entries", "stream=duration", "-of", "csv=p=0", voice,
  ], { encoding: "utf8" }).trim());
  if (!Number.isFinite(duration) || voiceStarts[index] + duration > voiceEnds[index] - 0.15) {
    throw new Error(`Voice ${index + 1} needs ${duration.toFixed(2)}s; allotted ${(voiceEnds[index] - voiceStarts[index]).toFixed(2)}s`);
  }
  console.log(`Voice ${index + 1}: ${duration.toFixed(2)}s`);
}

const args = ["-y", "-hide_banner", "-loglevel", "error"];
for (const [index, scene] of scenes.entries()) {
  args.push("-loop", "1", "-framerate", "30", "-t", String(scene.length + 0.35),
    "-i", path.join(frames, `scene-${index + 1}.png`));
}
for (let index = 0; index < narration.length; index++) {
  args.push("-i", path.join(media, `voice-${index + 1}.aiff`));
}

const filters = scenes.map((_, index) => `[${index}:v]fps=30,format=yuv420p,setpts=PTS-STARTPTS[v${index}]`);
let previous = "v0";
for (let index = 1; index < scenes.length; index++) {
  const next = `blend${index}`;
  filters.push(`[${previous}][v${index}]xfade=transition=fade:duration=0.35:offset=${scenes[index].at}[${next}]`);
  previous = next;
}
narration.forEach((_, index) => {
  filters.push(`[${scenes.length + index}:a]adelay=${Math.round(voiceStarts[index] * 1000)}:all=1[a${index}]`);
});
filters.push(`${narration.map((_, index) => `[a${index}]`).join("")}amix=inputs=${narration.length}:duration=longest:normalize=0,aresample=48000,acompressor=threshold=-21dB:ratio=2:attack=5:release=90,loudnorm=I=-16:TP=-1.5:LRA=7,apad=whole_dur=60,atrim=duration=60[a]`);
args.push("-filter_complex", filters.join(";"), "-map", `[${previous}]`, "-map", "[a]",
  "-t", "60", "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "19",
  "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output);
execFileSync(ffmpeg, args, { stdio: "inherit" });
console.log(`Video: ${output}`);
