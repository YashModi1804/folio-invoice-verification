# Live evaluation — 2026-09-16

Provider: Google Gemini, configured model `gemini-3.6-flash`. The user's key is
stored only in ignored `.env`. No billing settings were changed or verified.

## Completed extraction batch

Eleven inputs completed with schema-valid output and the expected routing:

| Input | Route | Key observation | Extraction + validation time |
| --- | --- | --- | --- |
| Northline PDF | Auto-approved | Total 1325.00; 3 lines | 15.870s |
| Alder two-page scan | Review | 6 lines; printed 1850.00 vs calculated 1800.00 | 14.747s |
| Meridian PDF | Review | Date null; total 810.00 reconciles | 10.271s |
| Microsoft Contoso invoice | Review | Correct total 110.00, not balance 610.00; missing charges remain null | 10.757s |
| Microsoft British invoice | Review | GBP 180.00; omitted shipping/discount remain null | 10.318s |
| Microsoft Invoice 1 | Review | Charges 56651.49; no invented line items | 11.487s |
| Microsoft Invoice 6 | Review | Total 10686.25; percentage-only tax left uncomputed | 17.965s |
| Northline JPEG | Auto-approved | Total 1325.00 | 8.777s |
| Northline PNG | Auto-approved | Total 1325.00 | 14.859s |
| Northline WEBP | Auto-approved | Total 1325.00 | 11.283s |
| Northline rotated PNG | Auto-approved | Total 1325.00 despite 90-degree rotation | 11.593s |

Batch totals reported by the provider: 14,591 input tokens, 9,146 output tokens,
10,739 reasoning tokens. These exclude diagnostic requests and browser/API smoke
tests. Estimated cost stays **null**, since billing tier and pricing are unverified.
Raw local reports: `data/evaluations/demo-pack.json` and `formats.json` (ignored).

## Compatibility fix

The account rejected the older model selection. Model discovery and an explicit
request established access to `gemini-3.6-flash`. The adapter now uses the current
REST `responseFormat.text` with the `APPLICATION_JSON` enum and an inlined
structural schema. The provider rejected the fuller Pydantic decoder schema.
Precision, finite amounts, field lengths, date formats and confidence bounds
remain enforced by the original Pydantic model after extraction. Regression tests
prove invalid amounts are still rejected.

Reference: [Google's generateContent REST contract](https://ai.google.dev/api/generate-content).

## Limitations and honest demo claims

- Eleven inputs represent seven layouts, with four variants of one invoice—not
  eleven independent layouts, a held-out benchmark, or an accuracy percentage.
- Timings exclude queue time and browser rendering. No p95 SLA is established.
- Confidence remains an uncalibrated model signal; evidence quotes are review aids.
- Two browser uploads after the batch encountered provider failures. A subsequent
  authenticated API upload identified `PROVIDER_RATE_LIMITED`; Google's diagnostic
  response confirmed HTTP 429 for `GenerateRequestsPerDayPerProjectPerModel-FreeTier`,
  reported limit **20 requests per day** for this project/model. A later retry after
  the suggested short delay still failed; that delay does not override the daily quota.
  End-to-end **live success through the browser/worker is not yet verified**;
  live extraction + validation succeeded through the evaluation runner. The full
  API/worker/review path is separately covered by offline integration tests.
  They became visible failed jobs; no invented extraction or financial approval
  was persisted. Do not hide these from reliability claims or erase their audit trail.
- Free-tier quotas can interrupt a recording. Rehearse once, avoid concurrent
  evaluation batches, and keep an honestly labeled offline fixture fallback.
- No testing of real client PII, handwriting, adverse camera scans, production
  concurrency, hosted security, or long-document extraction was performed.
