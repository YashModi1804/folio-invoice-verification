# Product review — November 3, 2026

Folio should help an agency CTO understand, in one minute, how an uncertain AI
extraction becomes a traceable business decision. This release prioritizes that
proof over adding more screens, providers, or accounting integrations.

## Release decision

**Conditional go for the existing, low-volume sales demo.** Publish after the final
integrated tests, browser review, CI, and deployed readiness checks pass. The
backend and security reviewers found no remaining blocker for that limited use.
This is not approval for confidential client data, unrestricted public file
processing, or a continuously available production service.

The static sample experience remains the dependable outreach fallback. The
repository records a November 6, 2026 expiry for the current Render database;
confirm this in the deployment dashboard before extending a live campaign.
Render documents free-service sleep and a 30-day free-database lifetime. A launch
page improves the waiting experience; it cannot remove those hosting limits.
[Render free-service documentation](https://render.com/docs/free).

## Team responsibilities and decisions

| Role | Decision for this release |
| --- | --- |
| Product manager | Keep the prospect journey and acceptance criteria focused; prioritize reliability and truthful evidence over feature count. |
| Backend engineer | Correct reviewed ERP exports, original-page citations, incomplete coverage, arithmetic extremes, and recoverable worker failures. |
| Security engineer | Bound anonymous admission and streamed bodies, isolate native parsing resources, preserve workspace isolation, and redact errors. |
| UX engineer | Prevent stale workspace data, make the full review queue reachable, recover from connection errors, and distinguish original extraction from reviewed values. |
| Release engineer / QA | Run integrated regressions, migrations, browser checks, dependency audits, CI, and deployed checks; record measured results. |

The PM discussed priorities and acceptance directly with backend, security, and
UX reviewers. Engineering changes are evaluated against the
same journey: open Folio, inspect a sample, understand its exception, check its
source, record a decision, and inspect the preserved original.

## Acceptance gates

| Gate | Observable pass condition |
| --- | --- |
| First visit | The shared launch link has a bounded wait, retry, and immediately usable sample-preview link. It redirects only after a valid readiness response. |
| Honest demonstration | All four samples remain visibly synthetic; HelixPoint retains 18 lines and the deliberate $125 discrepancy. No fixture is presented as live inference. |
| Private workspace | Guest A cannot read, preview, decide, export, or measure Guest B's records. Switching to operator access cannot leave guest data on screen. |
| Useful review | An unresolved item remains discoverable beyond the latest 100 documents. Its source evidence opens the correct physical PDF page. |
| Auditable correction | A corrected field says “Reviewed.” Its citation remains explicitly original. The original view restores the model's values and checks without losing the review decision. |
| Correct integration | ERP output reflects the effective reviewed checks and actual review approval time. Approval never converts incomplete page coverage into proof that all lines were checked. |
| Predictable failure | Unsupported input, oversized streams, invalid auth, capacity exhaustion, and provider errors produce safe, actionable responses. Impossible provider configuration does not loop forever. |
| Bounded parsing | Native inspection, text extraction, and previews run in short-lived subprocesses with timeout and concurrency limits. Timeout/crash/busy tests verify safe failures and child cleanup; real PDF/image tests preserve normal rendering. Linux resource limits and any macOS fallback are documented accurately. |
| Retention | Guest credentials and samples continue working; expired personal uploads are inaccessible, and cleanup deletes stored bytes and related records when the service runs. Usage caps survive deletion. |
| Release evidence | Python tests, lint/format, frontend tests/build, fresh migrations, dependency audits, and local workflow pass; CI and deployed checks then verify the published version. |

Focused backend regressions and frontend tests passed during implementation.
Final test totals and deployed status belong in the release verification report;
this decision memo does not substitute for that evidence.

The [release verification report](REVIEW_2026_11.md) now records passed local checks,
Ubuntu CI and the deployed synthetic workflow. The scoped sales-demo release passed
these gates; hosting continuity and client-production validation remain separate work.

## Next work, in priority order

1. **Resolve live-demo continuity before database expiry.** Preserve the static
   preview and document any live unavailability. Durable storage is a separate
   hosting decision; this release introduces no paid service.
2. **Measure public-demo load before expanding upload capacity.** This release
   adds bounded parser subprocesses; its timeout, concurrency and memory settings
   still need deployment verification on the free host. Resource isolation is not
   an operating-system security sandbox or proof against all malicious PDFs.
   Consider caching repeated page previews if real usage demonstrates that need.
3. **Validate one agency's actual workflow.** Use its authorized, non-sensitive
   invoice examples to measure extraction quality and reviewer effort. Choose one
   requested ERP mapping only after that requirement is concrete. Synthetic
   samples prove workflow behavior, not real-world extraction accuracy.
4. **Resolve redistribution and data-handling terms before client delivery.**
   No project license has been selected. PyMuPDF offers AGPL and commercial
   licensing; the applicable obligations need review before promising
   unrestricted proprietary reuse. This memo does not choose a license or make
   a legal-compliance determination.
   [PyMuPDF licensing documentation](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright).

Defer multi-worker scheduling, full account/organization management, SSO, billing,
new model adapters, and automatic ERP write-back until a client requirement
justifies their complexity. They do not strengthen the current one-minute proof
as much as a reliable source-to-decision workflow.

## Product claims and operating boundaries

Guests are separate browser credentials, not verified people. Clearing browser
storage loses that identity. New-workspace admission and global upload limits
protect shared resources; per-browser limits alone cannot establish per-person
fairness. Groq quotas apply at organization level, and actual limits must be read
from the account. Do not equate anonymous visitor count with available inference
capacity. [Groq rate-limit documentation](https://console.groq.com/docs/rate-limits).

Describe two-hour retention as access expiry followed by physical cleanup while
the service is running. Do not promise deletion at an exact minute or deletion
from a provider's systems. Keep confidential customer documents out of this demo.

Measure the sales story by whether a reviewer can explain the discrepancy and
find the original evidence, not by a high model confidence score. No new
visitor-tracking service is required for this release.
