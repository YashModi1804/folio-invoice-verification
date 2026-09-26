/** Assemble a 30-second, locally narrated Folio agency demo. */
import { createRequire } from "node:module";
import { execFileSync } from "node:child_process";
import { mkdir, readFile } from "node:fs/promises";
import path from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const root = path.resolve(import.meta.dirname, "..");
const media = path.join(root, "output", "video");
const frames = path.join(media, "frames");
const ffmpeg = process.env.FFMPEG_PATH ?? "/opt/homebrew/bin/ffmpeg";
const ffprobe = process.env.FFPROBE_PATH ?? "/opt/homebrew/bin/ffprobe";
const output = path.join(media, "folio-30s-voiced-demo.mp4");

const scenes = [
  {
    image: "01-source.png",
    mode: "full",
    label: "01 / INTAKE",
    narration: "Meet Folio, an invoice verification engine for operations teams.",
    duration: 5.35,
    voiceStart: 0.35,
  },
  {
    image: "02-final-page.png",
    mode: "full",
    label: "02 / SOURCE + EXTRACTION",
    narration:
      "This three-page synthetic invoice was extracted with Groq. The source stays beside the captured data.",
    duration: 6.35,
    voiceStart: 5.3,
  },
  {
    image: "04-ledger.png",
    mode: "full",
    label: "03 / INDEPENDENT CHECKS",
    narration:
      "Folio checks each line with decimal arithmetic and records the processing path.",
    duration: 6.35,
    voiceStart: 11.3,
  },
  {
    image: "05-review.png",
    mode: "focus",
    label: "04 / DECISION GATE",
    headline: "Automation stops.",
    narration:
      "Page coverage is incomplete, and the printed total is fifty dollars out. Automation stops for human review.",
    duration: 7.35,
    voiceStart: 17.3,
  },
  {
    image: "06-trace.png",
    mode: "focus",
    label: "05 / AUDIT + HANDOFF",
    headline: "A clear handoff.",
    narration:
      "Audit and provider trace stay visible. Approved records export through a versioned ERP contract.",
    duration: 6,
    voiceStart: 24.3,
  },
];

const escapeHtml = (value) =>
  value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");

async function renderFrame(page, scene, index) {
  const source = await readFile(path.join(media, "stills", scene.image));
  const image = `data:image/png;base64,${source.toString("base64")}`;
  const isFocus = scene.mode === "focus";
  await page.setContent(`
    <!doctype html><html><head><meta charset="utf-8"><style>
      * { box-sizing: border-box; }
      html, body { margin: 0; width: 1920px; height: 1080px; overflow: hidden; }
      body { font-family: Arial, Helvetica, sans-serif; background: #122b2e; }
      .stage { position: relative; width: 1920px; height: 1080px; overflow: hidden; }
      .screen { position: absolute; inset: 0; width: 1920px; height: 1080px; }
      .provenance { position: absolute; top: 28px; right: 34px; padding: 14px 22px;
        color: #f4f2e9; background: rgba(18,43,46,.94); border: 1px solid #648077;
        border-radius: 999px; font-size: 17px; letter-spacing: 1.5px; font-weight: 700; }
      .caption { position: absolute; bottom: 0; left: 0; right: 0; min-height: 150px;
        display: flex; align-items: center; gap: 44px; padding: 22px 70px;
        color: #f8f8f1; background: rgba(17,43,46,.97); }
      .caption .label { flex: 0 0 300px; color: #b8d2c6; font-size: 19px;
        font-weight: 700; letter-spacing: 2px; }
      .caption .line { font-size: 31px; line-height: 1.22; font-weight: 600; }
      .focus-panel { position: absolute; top: 0; bottom: 0; left: 0; width: 1090px;
        background: #142f32; color: #f9f7ef; padding: 170px 95px 80px; }
      .focus-panel .eyebrow { color: #b8d2c6; font-size: 22px;
        font-weight: 700; letter-spacing: 3px; }
      .focus-panel h1 { margin: 58px 0 42px; font-family: Georgia, serif;
        font-size: 82px; font-weight: 400; line-height: 1.06; }
      .focus-panel p { max-width: 820px; font-size: 36px; line-height: 1.3; }
      .focus-panel .footer { position: absolute; bottom: 70px; left: 95px;
        font-size: 19px; color: #b8d2c6; letter-spacing: 1px; }
      .focus-panel .mark { color: #d7a35e; }
    </style></head><body>
      <div class="stage">
        <img class="screen" src="${image}" alt="Recorded Folio interface">
        ${isFocus ? `
          <div class="focus-panel">
            <div class="eyebrow">${escapeHtml(scene.label)}</div>
            <h1>${escapeHtml(scene.headline)}</h1>
            <p>${escapeHtml(scene.narration)}</p>
            <div class="footer"><span class="mark">f /</span> FOLIO · VERIFIED WORKFLOWS</div>
          </div>
        ` : `
          <div class="caption">
            <div class="label">${escapeHtml(scene.label)}</div>
            <div class="line">${escapeHtml(scene.narration)}</div>
          </div>
        `}
        <div class="provenance">RECORDED GROQ · SYNTHETIC DEMO</div>
      </div>
    </body></html>
  `);
  await page.locator(".screen").evaluate((element) => element.decode());
  await page.screenshot({ path: path.join(frames, `scene-${index + 1}.png`) });
}

await mkdir(frames, { recursive: true });
const browser = await chromium.launch({
  headless: true,
  executablePath:
    process.env.CHROME_PATH ??
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
});
try {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  for (const [index, scene] of scenes.entries()) {
    await renderFrame(page, scene, index);
  }
} finally {
  await browser.close();
}

for (const [index, scene] of scenes.entries()) {
  const voice = path.join(media, `voice-${index + 1}.aiff`);
  execFileSync("say", ["-v", "Daniel", "-r", "190", "-o", voice, scene.narration]);
  const duration = Number(
    execFileSync(ffprobe, [
      "-v", "error", "-show_entries", "stream=duration", "-of", "csv=p=0", voice,
    ], { encoding: "utf8" }).trim(),
  );
  const nextStart = scenes[index + 1]?.voiceStart ?? 30;
  if (!Number.isFinite(duration) || scene.voiceStart + duration > nextStart - 0.1) {
    throw new Error(`Voice segment ${index + 1} is ${duration.toFixed(2)}s; its slot ends at ${nextStart}s`);
  }
  console.log(`Voice ${index + 1}: ${duration.toFixed(2)}s`);
}

const ffmpegArgs = ["-y", "-hide_banner", "-loglevel", "error"];
for (const [index, scene] of scenes.entries()) {
  ffmpegArgs.push(
    "-loop", "1", "-framerate", "30", "-t", String(scene.duration),
    "-i", path.join(frames, `scene-${index + 1}.png`),
  );
}
for (let index = 0; index < scenes.length; index++) {
  ffmpegArgs.push("-i", path.join(media, `voice-${index + 1}.aiff`));
}

const filters = scenes.map((_, index) =>
  `[${index}:v]fps=30,format=yuv420p,setpts=PTS-STARTPTS[v${index}]`,
);
let previous = "v0";
for (let index = 1; index < scenes.length; index++) {
  const next = `blend${index}`;
  const offset = [5, 11, 17, 24][index - 1];
  filters.push(
    `[${previous}][v${index}]xfade=transition=fade:duration=0.35:offset=${offset}[${next}]`,
  );
  previous = next;
}
scenes.forEach((scene, index) => {
  filters.push(`[${index + scenes.length}:a]adelay=${Math.round(scene.voiceStart * 1000)}:all=1[a${index}]`);
});
filters.push(
  `${scenes.map((_, index) => `[a${index}]`).join("")}amix=inputs=${scenes.length}:duration=longest:normalize=0,atrim=duration=30,aresample=48000[a]`,
);

ffmpegArgs.push(
  "-filter_complex", filters.join(";"),
  "-map", `[${previous}]`, "-map", "[a]",
  "-t", "30", "-r", "30",
  "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
  "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output,
);
execFileSync(ffmpeg, ffmpegArgs, { stdio: "inherit" });
console.log(`Video: ${output}`);
