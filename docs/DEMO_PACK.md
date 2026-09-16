# Live demonstration document pack

These are evaluation documents, not customer records. Synthetic source documents
go through the real model when uploaded with `PROVIDER=gemini`. The console's
three built-in sample buttons remain explicitly labeled **offline fixtures**.

## Rebuild locally

```sh
.venv/bin/python -m pip install -e '.[demo]'
.venv/bin/python scripts/build_demo_pack.py
.venv/bin/python scripts/fetch_public_samples.py
.venv/bin/python scripts/check_provider.py
.venv/bin/python scripts/evaluate_live.py output/pdf/*.pdf
```

Live evaluation sends the selected documents to Google and consumes the account's
quota. Free-tier eligibility is account-dependent. Never send client documents
without permission and an appropriate data-processing agreement. Keys, PDFs,
evaluation output, uploads, and the local database stay outside Git.

## Recording order and ground truth

| Document | Expected facts | Demonstration |
| --- | --- | --- |
| `output/pdf/01-northline-clean.pdf` | NLS-2026-0914; 2026-09-14; USD; 3 lines; subtotal 1250; tax 100; shipping 25; discount 50; total 1325 | Automatic approval when all evidence/confidence checks pass |
| `output/pdf/02-alder-scanned-discrepancy.pdf` | ALD-2026-0082; 2026-09-12; USD; 6 lines across 2 raster-only pages; subtotal 1700; tax 136; shipping 24; discount 60; printed total 1850 | Python calculates 1800; +50 variance must block automatic approval |
| `output/pdf/03-meridian-missing-date.pdf` | MER-2026-0047; date absent; USD; 2 lines; subtotal 750; tax 60; shipping/discount explicitly 0; total 810 | Correct arithmetic does not compensate for a missing required date |

The generator also places PNG, JPEG, WEBP and 90-degree-rotated PNG versions of
Northline in `data/demo-pack/images/`. They test format/orientation robustness,
not four independent invoice layouts. The scan is a controlled rasterization,
not evidence of performance on blurry camera photos or handwriting.

## Public challenge samples

Downloaded under `data/demo-pack/public/`, with source URLs and SHA-256 hashes in
`provenance.json`; the download script retains source repository license files.
These samples broaden layout coverage. They are not a representative benchmark.

| File | Source | What to inspect |
| --- | --- | --- |
| `azure-contoso-invoice.pdf` | [Microsoft Content Understanding assets](https://github.com/Azure-Samples/azure-ai-content-understanding-assets/blob/main/document/invoice.pdf) | Invoice total 110, **not** amount due 610; 3 lines; subtotal 100; tax 10; omitted shipping/discount must remain null |
| `azure-british-invoice.png` | [Microsoft Document Intelligence samples](https://github.com/Azure-Samples/document-intelligence-code-samples/blob/main/Data/invoice/invoice-english-britain.png) | GBP 180; subtotal 150; VAT 30; invoice 12345678; 2024-02-19; omitted shipping/discount |
| `azure-invoice-1.pdf` | [Azure Python SDK samples](https://github.com/Azure/azure-sdk-for-python/blob/master/sdk/formrecognizer/azure-ai-formrecognizer/samples/sample_forms/forms/Invoice_1.pdf) | Invoice 34278587; 2017-06-18; charges 56651.49; absent lines and breakdown require review |
| `azure-invoice-6.pdf` | [Microsoft Document Intelligence samples](https://github.com/Azure-Samples/document-intelligence-code-samples/blob/main/Data/invoice/Invoice-6.pdf) | Project statement 9876; subtotal 10375; total 10686.25; per-line discount and percentage-only tax are outside the simple invoice policy |

All four should require human review under the current conservative policy. Never
fill absent charges with zero to make these documents pass.

## 60-second Loom plan

Prepare a completed clean live run first. Upload Alder using **Choose document**,
not a fixture button. Keep the Gemini model label visible.

Live evaluation and diagnostics reached the account's 20-requests/day free quota
for the selected model. Check the
provider's quota/reset status before recording, then upload Northline and Alder
to verify the complete UI/worker path. Do not run the entire evaluation pack
immediately before Loom. No paid billing is necessary for the offline fallback.

1. **0–10s:** Show the two-page invoice: “A real model reads this synthetic scan.”
2. **10–25s:** Show the completed extraction and source page 2. If live processing
   is slow, cut the wait and label the cut; do not claim an edited duration as latency.
3. **25–40s:** Show the +50 total discrepancy and human-review route:
   “The model extracts; Python independently reconciles the amounts.”
4. **40–52s:** Show review and audit history. Reject or hold this invoice because
   its source is inconsistent. A mathematical result does not authorize changing
   a supplier's legal invoice; demonstrate a correction only as a labeled simulation.
5. **52–60s:** Show clean automatic approval and actual token/latency telemetry.
   Cost is unknown until billing is configured—not a fabricated dollar amount.

CTA: “Can we test this integration on a small, permissioned batch from one client?”
