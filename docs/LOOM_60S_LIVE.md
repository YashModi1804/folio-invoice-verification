# Folio — continuous 60-second live walkthrough

The deliverable is `output/video/folio-60s-live-demo.mp4`: a single continuous
1920 × 1080 browser recording at 30 fps, with local male narration. It replaces
the earlier still-image storyboard cut.

The operator actually navigates Folio: hovers the intake, searches and opens the
saved Groq challenge, inspects a cited field and changes source pages, scrolls
through the Decimal verification ledger, types an unsaved review note, opens a
separate corrected audit record, opens a separate approved fixture, and fetches
the actual ERP export from the local API. The last response is formatted for
legibility and labeled as such. There are no still-image scene cuts, no provider
request during recording, and no claim that the held challenge was exported.

| Time | Live action | Voiceover |
| --- | --- | --- |
| 0–7s | Intake and document register. | “For client invoices, extraction is only the start. Folio shows when the data should not be trusted.” |
| 7–17s | Search and open the saved Deltaforge Groq result. | “Each upload becomes a durable job. The worker inspects the PDF, selects pages within provider limits, and records its plan.” |
| 17–27s | Inspect model-cited evidence and move through the source pages. | “This recorded Groq run shows typed fields beside the synthetic source, with page references and actual token usage.” |
| 27–39s | Scroll through passed lines to incomplete subtotal and $50 total failure. | “Python checks captured lines and totals with decimal arithmetic. A skipped page stays incomplete, and a fifty-dollar variance blocks approval.” |
| 39–50s | Enter a draft review note, then show a separate correction and audit event. | “The exception enters human review. Corrections are appended; the original extraction, verification ledger, and audit history remain available.” |
| 50–60s | Show an approved fixture and a formatted live API export response. | “FastAPI, Pydantic, provider adapters, and durable jobs underpin Folio. Only approved records reach an idempotent ERP export.” |

The challenge selected pages 1 and 3 and skipped page 2 under provider capacity.
The subtotal is therefore incomplete rather than falsely marked valid. Its
printed total is 8,890.66; independent calculation yields 8,840.66. The audit
example is a separate local-inference run with a simulated vendor-confirmed
date; it does not imply the date was present in the source. The final export is
from a clearly labeled synthetic fixture and does not write to an ERP.

## Rebuild

Start Folio locally. Node must resolve Playwright, Playwright's free FFmpeg
recording helper must be installed (`npx playwright install ffmpeg`), and macOS
`say` plus FFmpeg/FFprobe must be available. On this workspace the bundled
runtime is under `.tools/node`; `NODE_PATH` points to its Playwright modules.
Then run `scripts/record_folio_live_60s.mjs` and
`scripts/render_folio_live_60s.mjs` with that Node runtime. The first script
records one continuous browser take from saved jobs without inference; the
second trims only browser startup, adds timed narration, and normalizes audio.

The scripts assert the required saved job IDs and ERP contract. Intermediate
video, audio, and metadata live under ignored `output/video/`. They are not
committed or pushed to GitHub.
