# Verification and scope report

## Verified locally

- Python 3.12; SQLite migration and separate worker startup.
- 51 automated tests, passing without live credentials.
- Ruff lint and formatting checks.
- TypeScript strict compilation and Vite production build.
- Three offline routing regression fixtures; not a live extraction benchmark.
- Browser login, document register, discrepancy submission, page evidence navigation,
  field correction, human approval, audit history, and effective corrected register amount.
- Source preview and invoice review render together at the normal desktop viewport.
- Tablet layout inspected at 900px; source and extracted data stack without overlap.
- Browser clean sample reaches automatic approval; corrected record summary displays 1250.00.

## Explicit implementation choices

- Single operator token; no tenant identities or role separation.
- Private local files served through authenticated endpoints; no public/signed source URLs.
- Database-backed queue and separate worker; no required Redis dependency.
- Immutable extraction/check snapshot in the job aggregate; separate relational audit and
  review records, rather than seven independently normalized tables.
- Provider failures are terminal `FAILED` jobs with safe codes. They do not create a
  reviewable financial record when there is no valid extraction.
- Original model confidences and evidence remain original after human corrections.
- Human approval permits a documented override of remaining arithmetic discrepancies.
- Unknown provider cost is null; no hardcoded pricing promise or fabricated token counts.
- Live Gemini integration is configurable. OpenAI was not added because the application
  is intended to use the user's selected free-tier model.
- Rendering uses 108 DPI for the demo. Dense real invoices may require tuning with a
  representative dataset. Evidence is page/text-based; bounding-box highlighting is deferred.
- Source retention is an explicit dry-run/apply command; it is not scheduled locally.

## Not yet verified

- A live Gemini request with a selected model and account key.
- Extraction accuracy, confidence calibration, or live p95 latency on client documents.
- Docker/PostgreSQL deployment; Docker is not installed in this environment.
- Production concurrency, load, backup/restore, public-hosting hardening, or compliance.

## Meaning of “production-grade” here

The demo demonstrates production engineering practices: schema validation, deterministic
checks, idempotent intake, durable jobs, explicit failure states, authentication, safe logs,
and retained review history. It is not evidence of production certification or benchmarked
extraction accuracy. Complete the client-specific deployment and evaluation work before
making those claims.
