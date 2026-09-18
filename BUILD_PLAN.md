# Build plan — 24 meaningful commits

1. Record scope, engineering rules, and delivery plan.
2. Bootstrap Python package, settings, and local tooling.
3. Define typed extraction and evidence contracts.
4. Implement deterministic currency reconciliation.
5. Implement conservative approval policy and tests.
6. Add explicit synthetic invoice fixtures.
7. Add relational persistence and versioned migrations.
8. Add bounded file inspection and private storage.
9. Add provider contract and transparent fixture adapter.
10. Add configurable Gemini adapter and bounded retries.
11. Add durable database job runner and recovery behavior.
12. Add authenticated intake, idempotency, and job endpoints.
13. Add review decisions and immutable audit history.
14. Add health, metrics, and structured processing logs.
15. Bootstrap React/TypeScript console and visual system.
16. Implement upload and sample selection workflow.
17. Implement document workspace and verification ledger.
18. Implement review editing and audit timeline.
19. Add queue filtering, telemetry, and responsive states.
20. Add end-to-end API and failure tests.
21. Add provider contract tests and evaluation runner.
22. Add Docker, CI, and VS Code tasks.
23. Verify browser interactions and fix integration issues.
24. Complete README, demo script, and acceptance report.

## Implementation decisions

Delivery status: all 24 planned slices implemented. See docs/ACCEPTANCE.md for measured
verification and explicit deployment/live-provider limitations. No GitHub remote was used.

- Working name: Folio. Single protected operator workspace.
- Start with invoices in USD/EUR/GBP; unsupported currencies route to review.
- React/TypeScript/Vite frontend; FastAPI/Pydantic/SQLAlchemy backend.
- SQLite for zero-install local demo; PostgreSQL through DATABASE_URL for deployment.
- A database-backed worker avoids a mandatory Redis service. Processing claims use
  atomic conditional updates. Ambiguous interrupted live requests fail for manual retry;
  no promise of exactly-once external provider billing.
- Gemini is opt-in with a user-provided free-tier key/model. No paid API default.
- Fixture results apply only to generated samples, never arbitrary uploaded files.
- Single operator token, private local document storage, seven-day retention command.
- Shipping, discounts, inclusive tax, incomplete lines, and missing evidence must
  explicitly prevent unsafe automatic approval.
- Model evidence is a reviewer aid, not independently verified provenance.
- Commit identity and remote are supplied by the user; do not invent attribution.

## Follow-up commit 25 — live verification and Loom pack

Use the saved local key without printing it; validate the provider adapter against
current API behavior; generate three labeled source PDFs and four image variants;
fetch four public Microsoft examples with provenance; record actual outcomes and
quota limitations; keep binaries, reports, credentials and databases untracked.

## Follow-up — local inference

Add an explicit Ollama provider, loopback-only transport and local-inference UI
labels. Preserve Gemini, immutable provenance, Decimal checks and review policy.
Test the adapter offline, then run the three acceptance documents through the
actual worker and record measured performance. Keep runtime/model files ignored.

## Follow-up — rehearsal reliability

Use one Gemini request per job, phase-specific timeouts, and an opt-in local
fallback only for availability failures. Record the cloud failure and actual
provider without changing verification policy. Benchmark a smaller local model,
rehearse the real API/review workflow, and preserve measured demo results.

Add Groq vision as an explicit alternative at the user's request. Enforce its
model-specific page/payload limits before inference; validate JSON locally, retain
actual provider provenance, and apply the same consent-based local fallback.
