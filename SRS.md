# SRS — Production-Grade AI Document Processing & Verification Engine

**Document status:** implementation-ready draft  
**Primary use:** a white-label sales demo and reusable backend foundation for agency client work  
**Success metric:** persuade an agency CTO, in a 60-second demo, that the system prevents bad financial data from silently entering a client's systems.

## 1. Product Definition

The product accepts an invoice, receipt, or purchase document; extracts a canonical invoice record with a vision-capable model; independently checks the result with deterministic code; and routes it to automatic approval or a human review queue.

This is not a consumer SaaS, a generic “chat with PDF” tool, or an autonomous accounting system. It is a focused proof of reliable AI integration that can be branded and adapted to a client's workflow.

### 1.1 Demo narrative

The product must make one promise visible: **the model may extract data, but it never gets to approve its own work.** A reviewer can see the source document, extracted values, validation results, confidence signals, and a precise reason for routing.

### 1.2 In scope

- Invoice/receipt image and PDF intake, including multi-page documents.
- Vision-model extraction into a strictly validated canonical schema.
- Deterministic financial reconciliation and data-quality checks.
- Configurable confidence policy and HITL routing.
- Persisted processing runs, results, audit events, and review decisions.
- A compact operator UI built for a credible demo, plus an OpenAPI endpoint.
- Provider abstraction supporting OpenAI and Gemini without leaking vendor code through the application.

### 1.3 Explicitly out of scope for v1

- Accounting-platform write-back, payment execution, tax calculation, and fraud detection.
- User-managed organizations, billing, SSO, and full RBAC. Demo access may use a single protected operator account.
- Training or fine-tuning models.
- Guaranteed legal/tax compliance or “zero hallucination” claims.

### Public demo extension

An optional public demo may issue an anonymous guest credential
without signup. Each browser retains its credential locally. Each guest receives a separate workspace with private uploads,
results, source pages, reviews, exports and metrics. Existing operator records
remain in the operator workspace. Synthetic fixture examples may be seeded into
each guest workspace but must stay visibly labeled and make no provider call.
Guest access and labeled synthetic samples do not expire by application policy.
Each guest upload, result and review history becomes inaccessible after two hours;
cleanup runs when the service is awake, so the UI must not promise physical deletion
at an exact minute. Guest live uploads have per-guest and site-wide daily caps.
This is a demo access model, not client authentication, SSO, or a data-retention
guarantee for third-party providers or the time-limited free database.

## 2. Corrections Applied to the Original Draft

| Original point | Correction in this SRS | Why it matters |
|---|---|---|
| “Zero-cost” while using commercial APIs | Describe it as **low-cost / free-tier demo capable**. Local demo mode must work without paid keys using fixtures; live AI inference is variable-cost. | Avoids a claim a CTO can immediately disprove. |
| `float` for currency | Use `Decimal` in Python and string/decimal numeric fields at the API boundary. | Binary floats can make valid financial totals fail by fractions of a cent. |
| One overall confidence + free-form reasoning | Require field-level confidence, evidence, and a policy-derived route; retain model notes only as non-authoritative diagnostics. | Confidence is an AI signal, not proof. The system needs explainable routing. |
| Synchronous “async processing” endpoint | Upload returns a job; a worker processes it; clients poll or subscribe to job state. A synchronous convenience endpoint is optional only for small demo files. | Vision calls and multi-page rendering can exceed web request limits. |
| `human_review_queue` as a separate copy of invoice data | Store one document, one extraction version, and a review task referencing that extraction. | Preserves audit history and prevents divergent records. |
| Hard-coded model pricing formula | Store a versioned model-price catalog in configuration and return the price version used. | Model names, token accounting, and prices change. |
| Swagger as the API UI | Keep `/docs`, but include a purposeful operator console. | The demo must feel like a workflow product, not an endpoint test. |

## 3. Target Users and Primary Flows

### 3.1 Personas

- **Agency CTO / buyer:** wants evidence that integrations are dependable, observable, and easy to adapt.
- **Client operations reviewer:** resolves exceptions without reading raw logs or guessing what failed.
- **Implementation engineer:** changes provider, schema, policy, or destination with clear extension points.

### 3.2 Approval flow

1. Operator uploads a document and the API creates a processing job.
2. The worker validates file safety, renders PDF pages, and performs structured extraction.
3. Validation code reconciles amounts and evaluates required fields and confidence policy.
4. A passing record is persisted as `AUTO_APPROVED`; the dashboard shows the source, values, checks, latency, and cost.

### 3.3 Review flow

1. Any failed integrity check, missing required field, low-confidence core field, or processing anomaly creates `REQUIRES_HUMAN_REVIEW`.
2. The reviewer sees exact route reasons and source-page evidence next to the extracted fields.
3. The reviewer corrects values, approves or rejects the record, and must supply a reason for rejection.
4. The system writes an immutable audit event; the original model result is never overwritten.

## 4. Architecture and Boundaries

```text
Browser / API client
        │ upload
        ▼
FastAPI API ──► Object storage (original + rendered pages)
        │ creates job
        ▼
Worker / queue ──► Provider adapter ──► OpenAI or Gemini
        │                    │ structured response + usage
        ▼                    ▼
Validation + routing policy ──► PostgreSQL
        │                         │
        └──────── Operator console / review queue ◄┘
```

**Preferred implementation:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy/Alembic, PostgreSQL/Supabase, PyMuPDF, and a small worker queue. Use provider-native structured output where available; `Instructor` is allowed as an adapter, not a framework dependency that shapes the domain model.

### 4.1 Design constraints

- All financial arithmetic uses `Decimal`, explicit currency, and a documented rounding rule (`ROUND_HALF_UP`, two minor units unless the currency configuration says otherwise).
- Extraction output is untrusted until schema, evidence, and deterministic checks complete.
- API keys and document URLs never appear in logs, browser payloads, or telemetry.
- Original documents are private and expire according to a configurable retention policy.
- Each provider request has a bounded timeout, idempotency protection, and a recorded provider/model/version. Gemini is attempted once per job; no automatic cloud replay after errors that may already consume quota.
- Every public response includes a `correlation_id`; logs and audit events use the same ID.

## 5. Functional Requirements

### FR-1 — Intake and job creation

- `POST /api/v1/documents` MUST accept `multipart/form-data` with PDF, PNG, JPEG, or WEBP files.
- The server MUST enforce configurable limits (default: 20 MB, 20 pages), MIME sniffing, extension allow-listing, and a generated object key; it MUST not trust the uploaded filename or MIME header.
- The endpoint MUST return `202 Accepted` with `document_id`, `job_id`, `status: QUEUED`, and `correlation_id`.
- Repeating a request with the same idempotency key and file checksum MUST return the original job rather than create a duplicate charge.
- Unsupported, password-protected, corrupt, or limit-exceeding files MUST end in a terminal, user-readable failure state without an unhandled 500 error.

### FR-2 — Rendering and extraction

- PDF pages MUST be rendered with PyMuPDF at a configurable resolution suitable for tables; the system MUST retain page number and image dimensions.
- The extraction request MUST supply only document pages and a versioned schema/prompt. No document-derived instructions may alter the system task or validation policy.
- The provider adapter MUST return schema-valid JSON or a typed extraction failure. It MUST not pass arbitrary LLM text into persistence.
- Core data: vendor name, invoice number, invoice date, currency, line items, subtotal, tax amount, shipping amount, discount amount, total amount, and source evidence.
- Fields that cannot be read MUST be `null` where allowed; the model must never invent placeholder business data to satisfy a required field.
- The system MUST record provider model, prompt/schema version, provider request ID where available, and token/usage data.

### FR-3 — Schema and data validation

- Domain schemas MUST be Pydantic v2 models. Monetary values MUST parse as `Decimal`; dates MUST parse as ISO-8601 `date`; currency MUST be ISO-4217 when present.
- `invoice_number`, `invoice_date`, `currency`, and `total_amount` are core fields. A missing core field is a route reason, not a server exception.
- Every critical field (`vendor_name`, `vendor_tax_id` when present, `invoice_number`, `invoice_date`, `currency`, `subtotal`, `tax_amount`, `total_amount`) MUST include a confidence score in `[0, 1]` and evidence references (`page_number`, quoted source text, optional bounding box).
- Model-provided “reasoning” MUST NOT be stored or shown as chain-of-thought. Store a short, structured `extraction_note` and evidence only.

### FR-4 — Deterministic verification

All comparisons use the configured currency tolerance (default `0.01`). Missing values generate an explicit failed/inconclusive check; they do not silently become zero.

For line items with complete quantities and unit prices:

```text
calculated_line_total = round(quantity × unit_price)
calculated_subtotal   = sum(calculated_line_total)
calculated_total      = subtotal + tax + shipping - discount
variance              = extracted_total - calculated_total
```

- The engine MUST verify each supplied `line_total` against quantity × unit price, if all three are present.
- The engine MUST compare item subtotal to extracted subtotal when sufficient complete line data exists.
- The engine MUST compare extracted total to `subtotal + tax + shipping - discount` whenever those inputs exist.
- `math_validated` is `true` only when all applicable checks pass. It is `null` when the check is not applicable because data is absent; such absence is independently evaluated by routing policy.
- The response and persistence layer MUST retain individual check results, expected amount, observed amount, variance, tolerance, and failure code.

### FR-5 — Routing policy and HITL

- A record is `AUTO_APPROVED` only when: schema validation passes; all required checks pass; all required core fields exist; and every required core field meets the configured threshold (default `0.85`).
- Any failed verification, absent required core field, confidence below threshold, ambiguous multi-invoice document, or provider processing anomaly MUST create a `REQUIRES_HUMAN_REVIEW` task.
- Routing MUST be a pure, unit-tested policy function that returns machine-readable route reasons; it MUST not be decided by the model.
- Reviewers MUST be able to approve with corrections or reject. Approval after review results in `HUMAN_APPROVED`; rejection results in `REJECTED`.
- A manual decision MUST capture actor, timestamp, changed fields (before/after), note, and extraction version.

### FR-6 — Operator console

The UI is a small, high-signal operational instrument—not a generic analytics dashboard.

- **Upload view:** a restrained drop zone with file limits, sample-document buttons, and a short statement of the verification promise.
- **Processing view:** document preview, visible stepper (`Uploaded → Extracted → Verified → Routed`), live job state, elapsed time, and a terminal-safe error explanation.
- **Result view:** source page on the left; extracted invoice summary and validation ledger on the right. Use a clear “approved” or “needs review” decision banner, with route reasons visible at first glance.
- **Review queue:** cards/table prioritised by severity and age. Opening an item reveals field-level evidence and correction controls, not raw JSON by default.
- **Telemetry drawer:** show model, prompt/schema version, input/output usage, estimated cost, latency, and correlation ID. This supports the CTO conversation without overwhelming the reviewer.
- Visual direction: calm, editorial, document-centric; use generous whitespace, an ink/navy base, one warm amber for review, and a reserved green for passed checks. Avoid stock gradient cards, excessive charts, emoji, fake activity feeds, and “AI magic” language.
- Responsive support is required for laptop and tablet widths; document review is optimized for desktop.

### FR-7 — API and observability

- `GET /api/v1/jobs/{job_id}` MUST expose job lifecycle, result summary, route reasons, and telemetry without exposing signed source URLs to unauthenticated callers.
- `GET /api/v1/review-tasks` and `POST /api/v1/review-tasks/{id}/decision` MUST support review operations.
- Health endpoints MUST distinguish API liveness from database, storage, and queue readiness.
- Structured logs MUST include correlation ID, event name, status, duration, provider/model, and safe error code. They MUST exclude document text, credentials, and personal data by default.
- Metrics MUST include job counts by terminal status, extraction failure rate, review rate, verification failure rate, p50/p95 latency, and estimated cost per document.

## 6. Canonical Domain Contracts

```python
from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    page_number: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=300)
    bbox: tuple[float, float, float, float] | None = None


class ExtractedField(BaseModel):
    value: str | Decimal | date | None
    confidence: float = Field(ge=0, le=1)
    evidence: list[Evidence] = Field(default_factory=list)
    extraction_note: str | None = Field(default=None, max_length=240)


class LineItem(BaseModel):
    description: ExtractedField
    quantity: ExtractedField
    unit_price: ExtractedField
    line_total: ExtractedField


class VerificationCheck(BaseModel):
    code: str
    state: Literal["PASS", "FAIL", "NOT_APPLICABLE"]
    expected: Decimal | None = None
    observed: Decimal | None = None
    variance: Decimal | None = None
    tolerance: Decimal | None = None


class ProcessingTelemetry(BaseModel):
    latency_ms: int = Field(ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: Decimal | None = None
    pricing_version: str | None = None
    provider: str
    model: str


class ExtractionResponse(BaseModel):
    document_id: str
    job_id: str
    status: Literal["QUEUED", "PROCESSING", "AUTO_APPROVED", "REQUIRES_HUMAN_REVIEW", "FAILED"]
    route_reasons: list[str]
    checks: list[VerificationCheck]
    telemetry: ProcessingTelemetry | None = None
    correlation_id: str
```

Implementation note: production code may use narrower generic models than the illustrative union above. Keep the external API stable and serialize `Decimal` as JSON strings or documented decimal numbers consistently.

## 7. Persistence Model

| Entity | Required purpose |
|---|---|
| `documents` | file metadata, checksum, content type, page count, storage key, retention timestamp |
| `processing_jobs` | lifecycle, idempotency key, correlation ID, provider/model, attempts, safe failure details |
| `extractions` | versioned normalized extraction, schema/prompt version, confidences, evidence, raw provider response in restricted storage if retained |
| `verification_checks` | one row per deterministic check with values and result |
| `review_tasks` | task status, severity, route reasons, owner, opened/resolved timestamps |
| `review_decisions` | immutable reviewer action, changes, decision note, actor, timestamp |
| `audit_events` | append-only business events tied to document/job/extraction/review IDs |
| `model_price_catalog` | provider/model input/output pricing, effective date, currency, version |

Use foreign keys and immutable extraction versions. `review_tasks` references an extraction; it does not duplicate its financial fields.

## 8. Non-Functional Requirements

| Area | Requirement |
|---|---|
| Reliability | Job execution is retry-safe; terminal results are idempotent; provider timeouts/errors become visible failures or review tasks, never silent drops. |
| Performance | For a 1–3 page normal invoice, target p95 completion under 30 seconds in the demo environment, excluding provider outages. |
| Security | Secrets server-side only; short-lived signed document URLs; file validation; authenticated operator endpoints; audit logging; configurable document retention/deletion. |
| Privacy | Do not log raw document content; document access is least-privilege; state clearly that demo fixtures contain no real customer data. |
| Accessibility | Keyboard-operable controls, visible focus, semantic form errors, contrast-compliant status indicators; status is never communicated by color alone. |
| Maintainability | Layer boundaries: API, application orchestration, domain validation/routing, provider adapters, repositories. No business rules in routes, templates, or prompts. |
| Testability | Fixtures cover clean invoice, blurry scan, multi-page invoice, missing totals, mismatched math, null optional fields, provider malformed JSON, retry, and manual correction. |

## 9. Acceptance Criteria

The v1 demo is complete only when all of the following are demonstrable:

1. A multi-page sample PDF creates a job and reaches a terminal state without page-order loss.
2. A valid sample invoice is auto-approved with persisted extraction, checks, telemetry, and audit event.
3. A deliberately inconsistent invoice is routed to review with a visible total variance and specific check failure.
4. A low-confidence required field routes to review even when arithmetic passes.
5. A reviewer corrects a value and approves it; the original extraction and the before/after change remain visible.
6. A malformed provider response and an unsupported file produce safe, actionable failures rather than stack traces.
7. The test suite covers routing and arithmetic rules independently of any live model call.
8. The UI can tell the approval/review story without opening Swagger; `/docs` remains available for technical buyers.

## 10. Demo Script (60 Seconds)

| Time | Screen | Proof point |
|---|---|---|
| 0:00–0:10 | Upload a messy multi-page invoice in the operator console. | Real document intake, not pasted text. |
| 0:10–0:23 | Processing stepper advances; show page preview and job telemetry. | Observable AI workflow with controlled cost and latency. |
| 0:23–0:38 | Open result: total check fails by a visible amount; decision banner says “Needs human review.” | Code, not the model, protects data integrity. |
| 0:38–0:52 | Open review task, click field evidence on the source page, correct/approve. | HITL is practical and auditable. |
| 0:52–1:00 | Show audit trail and API response/OpenAPI in a secondary pane. | Reusable, integration-ready backend engineering. |

Use two prepared fixtures: one clean auto-approved invoice and one intentionally inconsistent invoice. Do not manufacture failures live; reliability is the message.

## 11. Delivery Plan

### Milestone A — Trustworthy core

Implement schema, provider interface, rendering, deterministic checks, routing policy, fixtures, and unit tests. Deliver a working API plus local/demo persistence.

### Milestone B — Audit-ready workflow

Add PostgreSQL migrations, object storage abstraction, async job runner, observability, review-task persistence, and manual decision audit trail.

### Milestone C — Sales-quality experience

Build the operator console, prepare deterministic demo fixtures, add deployment configuration, a concise README, architecture diagram, and a 60-second demo script.

## 12. Engineering Instructions for the Implementing Engineer

- Read this SRS before coding. First inspect the repository and preserve unrelated user changes.
- Build the smallest vertical slice that proves the acceptance criteria; do not add authentication, dashboards, framework abstractions, or integrations not needed by this SRS.
- Favor direct, typed Python: short functions, explicit names, narrow interfaces, early returns, and domain-specific error codes. Avoid clever metaprogramming, speculative abstractions, and “manager/service/helper” layers with no domain purpose.
- Write tests with deterministic fixtures before depending on live model credentials. A demo mode must allow a reviewer to run the full flow locally without an API key.
- Keep provider-specific SDK calls behind one adapter interface. Keep validation and routing pure and independently testable.
- Use migrations for persistent schema changes. Never persist secrets or raw document text in application logs.
- Before declaring completion, run formatting, type/lint checks if configured, and the relevant test suite; report exact commands and any unverified integrations.

## 13. Decisions Needed Before Production Deployment

These decisions are not blockers for the local sales demo, but must be explicitly chosen per client:

- The first supported currencies and their rounding/tolerance policy.
- Document-retention duration and deletion workflow.
- Identity/authorization model and reviewer roles.
- Queue/runtime choice and deployment region.
- The live model/provider, approved data-processing terms, and price catalog version.
- The client’s system of record and idempotent write-back contract.

## 14. Local inference extension

Ollama is an optional real-inference provider, distinct from deterministic fixtures.
It must use loopback transport with cloud features disabled, preserve Gemini as
an explicit alternative, and never silently fall back to a hosted provider.
The same Pydantic validation, Decimal checks and review policy apply. Provider
selection is pinned to each uploaded job and is not relabeled after settings change.
Local latency is measured separately; no cloud-equivalent performance is promised.
Zero API fees exclude hardware and electricity costs. Model output remains untrusted.

An opt-in Gemini-to-local fallback is permitted for transport, quota, and service
availability failures only. Consent is captured on the upload audit event; existing
jobs do not acquire fallback consent when configuration changes. The cloud failure
is audited before local inference. The result displays its actual provider, and
cloud usage/cost remains unknown when no response was received. No fallback is
allowed to conceal schema errors or failed verification. Local-to-cloud fallback
is never automatic.

## 15. Groq vision extension

Groq is an explicitly selected cloud provider, not a silent fallback between cloud
accounts. Its JSON-mode output must pass the identical Pydantic and financial
checks. Enforce documented model limits before requests: Qwen 3.8 27B permits
three page images, Qwen 3.6 27B five, with a 20 MB serialized request limit.
The UI must expose the active page limit. Groq may use the same consented local
recovery path as Gemini, with the actual failed provider named in audit history.
