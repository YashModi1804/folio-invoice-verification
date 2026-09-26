/** Add timed narration to one continuous Playwright recording; no still-image scenes. */
import { execFileSync } from "node:child_process";
import { readFile } from "node:fs/promises";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const media = path.join(root, "output", "video", "folio-live-60s");
const recording = JSON.parse(await readFile(path.join(media, "recording.json"), "utf8"));
const output = path.join(root, "output", "video", "folio-60s-live-demo.mp4");
const ffmpeg = process.env.FFMPEG_PATH ?? "/opt/homebrew/bin/ffmpeg";
const ffprobe = process.env.FFPROBE_PATH ?? "/opt/homebrew/bin/ffprobe";

const narration = [
  "For client invoices, extraction is only the start. Folio shows when the data should not be trusted.",
  "Each upload becomes a durable job. The worker inspects the PDF, selects pages within provider limits, and records its plan.",
  "This recorded Groq run shows typed fields beside the synthetic source, with page references and actual token usage.",
  "Python checks captured lines and totals with decimal arithmetic. A skipped page stays incomplete, and a fifty-dollar variance blocks approval.",
  "The exception enters human review. Corrections are appended; the original extraction, verification ledger, and audit history remain available.",
  "FastAPI, Pydantic, provider adapters, and durable jobs underpin Folio. Only approved records reach an idempotent ERP export.",
];
const starts = [0.38, 7.38, 17.38, 27.38, 39.38, 50.38];
const ends = [7, 17, 27, 39, 50, 60];

for (const [index, line] of narration.entries()) {
  const voice = path.join(media, `voice-${index + 1}.aiff`);
  execFileSync("say", ["-v", "Daniel", "-r", "175", "-o", voice, line]);
  const duration = Number(execFileSync(ffprobe, [
    "-v", "error", "-show_entries", "stream=duration", "-of", "csv=p=0", voice,
  ], { encoding: "utf8" }).trim());
  if (!Number.isFinite(duration) || duration < 0.5 || starts[index] + duration > ends[index] - 0.12) {
    throw new Error(`Voice ${index + 1} needs ${duration.toFixed(2)}s; its slot ends at ${ends[index]}s`);
  }
  console.log(`Voice ${index + 1}: ${duration.toFixed(2)}s`);
}

const args = [
  "-y", "-hide_banner", "-loglevel", "error",
  "-ss", String(recording.startOffsetSec), "-i", recording.rawPath,
];
for (let index = 0; index < narration.length; index++) {
  args.push("-i", path.join(media, `voice-${index + 1}.aiff`));
}
const filters = ["[0:v]fps=30,scale=1920:1080:flags=lanczos,trim=duration=60,setpts=PTS-STARTPTS[v]"];
narration.forEach((_, index) => {
  filters.push(`[${index + 1}:a]adelay=${Math.round(starts[index] * 1000)}:all=1[a${index}]`);
});
filters.push(`${narration.map((_, index) => `[a${index}]`).join("")}amix=inputs=${narration.length}:duration=longest:normalize=0,aresample=48000,acompressor=threshold=-21dB:ratio=2:attack=5:release=90,loudnorm=I=-16:TP=-1.5:LRA=7,apad=whole_dur=60,atrim=duration=60[a]`);
args.push(
  "-filter_complex", filters.join(";"), "-map", "[v]", "-map", "[a]", "-t", "60",
  "-r", "30", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
  "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output,
);
execFileSync(ffmpeg, args, { stdio: "inherit" });
console.log(`Continuous live demo: ${output}`);
