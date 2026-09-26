# Folio — earlier storyboard cut (superseded)

This still-image cut was superseded by the
[continuous live UI recording](LOOM_60S_LIVE.md). Keep this file only as the
original approved voiceover/storyboard reference.

The finished 1920 × 1080, 30 fps video is
`output/video/folio-60s-agency-demo.mp4`. It uses captured Folio UI, a saved
Groq extraction, two separately labeled synthetic examples, local macOS Daniel
voice, and no new provider request.

| Time | Shot | Voiceover |
| --- | --- | --- |
| 0–7s | Intake workspace. | “For client invoices, extraction is only the start. Folio shows when the data should not be trusted.” |
| 7–17s | Deltaforge source beside its held result. | “Each upload becomes a durable job. The worker inspects the PDF, selects pages within provider limits, and records its plan.” |
| 17–27s | Typed fields, then actual provider/page trace. | “This recorded Groq run shows typed fields beside the synthetic source, with page references and actual token usage.” |
| 27–39s | Decimal verification ledger: 11 passing line checks, incomplete subtotal, $50 total variance. | “Python checks captured lines and totals with decimal arithmetic. A skipped page stays incomplete, and a fifty-dollar variance blocks approval.” |
| 39–50s | Deltaforge review form, then a separately labeled local-inference record with a corrected date and audit event. | “The exception enters human review. Corrections are appended; the original extraction, verification ledger, and audit history remain available.” |
| 50–60s | Architecture card, then selected fields from a separately labeled approved fixture's actual ERP export response. | “FastAPI and durable workers make Folio reusable. Only approved records reach its versioned, idempotent ERP export.” |

The page plan selected pages 1 and 3 and skipped page 2 for the Groq challenge.
The subtotal is therefore **incomplete**, not mathematically disproved. The total
check is independently failed: printed 8,890.66 versus calculated 8,840.66.
The separate reviewed example uses a simulated vendor-confirmed date; the date
is not presented as if read from the PDF. The final ERP screen is a **selected-field
excerpt** of a real response, not a flat JSON schema or an outbound ERP write.

## Rebuild

Start the local app with `.venv/bin/python scripts/dev.py` if it is not already
running. The scripts use the local demo token by default; override with
`FOLIO_DEMO_TOKEN` when needed. Run:

```sh
NODE_PATH=/path/to/node_modules node scripts/capture_folio_60s.mjs
NODE_PATH=/path/to/node_modules node scripts/render_folio_60s.mjs
```

The capture checks the saved job states, $50 variance, a real correction audit,
and the approved `folio.erp-export.v1` contract before rendering. It never uploads
a document or calls an inference provider. The renderer needs Chromium,
Playwright, FFmpeg/FFprobe, and the local macOS `say` voice. Captures, narration,
manifest, and final video live under ignored `output/video/`; the reusable scripts
are committed without credentials or client documents.
