# Live demo readiness — 18 September 2026

## Recommended setup

Use Groq `qwen/qwen3.8-27b` as the primary and Ollama
`qwen3-vl:4b-instruct` as the explicit local availability fallback. Both keys remain
in ignored `.env`; never screen-share that file. Keys pasted into a chat should be
rotated before client use. No GitHub account or remote was used.

Start the two local processes in separate terminals:

```sh
.venv/bin/python scripts/local_model.py
.venv/bin/python scripts/dev.py
```

Do not start duplicates if they are already running. Then run:

```sh
.venv/bin/python scripts/preflight.py
```

The preflight checks local readiness, installed fallback model, pending jobs and
source files; it does **not** call a cloud model or guarantee available quota.
Open http://127.0.0.1:8000 using the local-only token `local-demo-only`.

## What was verified

### Final paced API/worker run — all primary Groq, no fallback

| Document | End-to-end worker time | Decision | Saved job |
| --- | --- | --- | --- |
| Northline clean | 3.545 s | Auto-approved | `accffb4e-071e-43ff-96d0-b0e49d0e1293` |
| Alder two-page scan | 3.197 s | Review: +50.00 variance | `b3c7e3cd-4e2d-4484-93da-c5ab3e393ab7` |
| Meridian missing date | 2.969 s | Review: date remains null | `bcea3d06-9457-48ac-b042-6df12f6e7adf` |

All three were checked against source ground truth for invoice number, date,
currency, subtotal/tax/shipping/discount/total, every quantity/unit price/line total,
and the expected policy decision. Duplicate uploads returned the same job; page
previews and audit endpoints worked. These timings include rendering, extraction
and verification, but exclude queue wait and UI polling. Requests were spaced by
65 seconds to respect free-tier constraints. Report: `data/evaluations/groq-final-workflow.json`.

An additional public Microsoft Contoso sample completed in 2.239 seconds: it
correctly extracted invoice total 110 (not balance due 610), retained omitted
shipping/discount as null, and required review. This is a fourth layout check,
not proof of general accuracy. Report: `data/evaluations/groq-public-contoso.json`.

### Diagnostics and recovery checks

- Groq credential/model access returned HTTP 200. Its currently accessible vision
  model is Qwen 3.8 27B, limited to three page images. The UI and intake enforce this.
- A real two-page Groq extraction completed in 3.145 seconds; all six lines were
  extracted and the deterministic total check found +50.00. A separate API/worker
  run took 3.158 seconds and persisted a review record.
- A clean Groq extraction completed in 2.967 seconds and was auto-approved.
- The full three-document API suite passed with explicit local recovery when Groq
  rate-limited back-to-back requests. These are not counted as three Groq successes.
- A real browser upload of Meridian reached review, a simulated reviewer supplied
  a date, and the audit recorded the correction. Original extraction date remains
  null; reviewed date is a separate snapshot (2026-09-18).
- Gemini 3.6 Flash returned service-unavailable errors, including with the replacement
  credential. Model metadata access worked. Gemini 3.1 Flash-Lite successfully
  extracted the same challenge in 6.506 seconds and is saved as an explicit alternative.
- One real Gemini-to-local recovery completed in 71.666 seconds, including a 20.796
  second cloud attempt. This is a recovery demonstration, not a fast-cloud benchmark.
- Ollama 4B with the final prompt passed all three expected policies. Local latency
  varied considerably: approximately 40–66 seconds on this M4 during these runs.
- The smaller 2B model was faster (roughly 15–27 seconds), but repeatedly mislabeled
  tax-inclusive invoices and failed the public project-statement schema. It was
  **not** promoted. Faster is not better if it hides the intended reconciliation.

These are small, controlled checks, not an accuracy benchmark or a p95 claim.
Current safe behavior matters more than a universal “no failures” promise.

## Quota and recovery behavior

Groq's free-tier quota prevented several rapid consecutive requests. Its safe
rate-limit headers are now captured in fallback audit events. Each job makes one
cloud attempt, never a hidden retry loop. Output generation is capped at 4096
tokens; truncated or malformed JSON fails safely rather than being repaired into
an apparently valid invoice. The cap can limit dense documents.

Allow at least a minute after the last Groq extraction before recording. This is a
rehearsal precaution, not a quota guarantee; account limits may differ. If quota
is exhausted, local recovery is slower and explicitly labeled. Do not re-upload
repeatedly during a recording; use the saved result or cut the wait honestly.

Only transport, quota and service availability errors permit local recovery.
Schema failures, absent fields and mathematical discrepancies do not trigger
another model to obtain a more convenient answer. Cloud-to-cloud switching is
manual. Local recovery does not imply the earlier cloud request was free: unknown
cost is null. The job retains requested and actual providers.

## Recording plan — 60 seconds

Use `output/pdf/02-alder-scanned-discrepancy.pdf`, a clearly labeled synthetic
two-page raster scan. It is not a customer document or a handwriting benchmark.
The printed total is 1850; six line items sum to 1700; tax 136, shipping 24 and
discount 60 imply 1800. Do not “correct” the extraction simply to make the math pass.

| Time | Screen | Narration |
| --- | --- | --- |
| 0–8s | Choose the two-page PDF; show the Groq/live label. | “The model reads the invoice. It does not get to approve its own work.” |
| 8–18s | Show source and extracted values. | “This synthetic scanned invoice has six line items across two pages.” |
| 18–32s | Total evidence on page two, then verification ledger. | “The printed total is 1,850. Decimal arithmetic calculates 1,800. That difference blocks automatic approval.” |
| 32–45s | Review note and reject the inconsistent invoice. | “A reviewer can request a corrected invoice. The original extraction stays untouched.” |
| 45–54s | Audit trail and processing trace. | “Provider, usage, processing time and the decision are recorded. A provider outage can recover locally, without hiding what happened.” |
| 54–60s | Saved clean verified record. | “I can adapt this pipeline to your client's document workflow and system of record.” |

For a correction demonstration instead, use Meridian's missing date and explain
that vendor confirmation is simulated. Do not invent a date and imply it came
from the PDF. Keep the Alder review record unresolved until recording.

Trim only idle waiting. If you cut a longer wait, add “Processing wait shortened”
and leave measured latency visible in the trace. Do not splice a fixture result
after a real upload or label local recovery as Groq output. This repository contains
the prepared demo and script, not a recorded or edited Loom video.

## Re-run acceptance deliberately

```sh
.venv/bin/python scripts/check_local_workflow.py --provider groq --require-primary --interval 65 --output data/evaluations/groq-final-workflow.json
```

This makes three live cloud requests. It fails if a local fallback is used, even
when the recovered result is correct. Default unit tests make no live model calls.
Reports, source PDFs, local model weights and the database remain ignored by Git.

Sources checked: [Groq vision](https://console.groq.com/docs/vision),
[Groq reasoning](https://console.groq.com/docs/reasoning),
[Gemini thinking configuration](https://ai.google.dev/gemini-api/docs/generate-content/thinking).
