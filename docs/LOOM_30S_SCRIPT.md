# Folio — 30-second narrated agency demo

The finished video is `output/video/folio-30s-voiced-demo.mp4` (1920 × 1080, 30 fps).
It uses Playwright captures of the actual Folio workspace, timed transitions, captions,
and the free local macOS **Daniel** synthetic voice. The video uses a saved Groq
result from a **synthetic evaluation invoice**; recording made no provider request.

| Time | Visual | Spoken line |
| --- | --- | --- |
| 0–5s | Three-page Deltaforge document beside extracted fields and the review banner. | “Meet Folio, an invoice verification engine for operations teams.” |
| 5–11s | Source invoice final page and the extracted totals side by side. | “This three-page synthetic invoice was extracted with Groq. The source stays beside the captured data.” |
| 11–17s | Audit trail and passed line checks in the independent ledger. | “Folio checks each line with decimal arithmetic and records the processing path.” |
| 17–24s | Incomplete subtotal, $50 total variance, and the reviewer decision. | “Page coverage is incomplete, and the printed total is fifty dollars out. Automation stops for human review.” |
| 24–30s | Reviewer decision and provider trace, including tokens, latency, and selected pages. | “Audit and provider trace stay visible. Approved records export through a versioned ERP contract.” |

The top-right label says **Recorded Groq · Synthetic demo** throughout. The source is
an evaluation challenge, not a customer invoice. The record is held for review;
the final line describes what Folio can do with *approved* records through its
versioned ERP export endpoint, not an export of this held record.

## Rebuild

Start the local app with `.venv/bin/python scripts/dev.py`, then run
`scripts/capture_folio_demo.mjs` followed by `scripts/render_folio_demo.mjs`
using Node with Playwright available. The renderer also needs the free macOS `say`
voice and FFmpeg. Intermediate frames and audio remain under ignored `output/video/`.
