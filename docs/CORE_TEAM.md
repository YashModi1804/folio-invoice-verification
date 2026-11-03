# Folio core team

The team's purpose is to make a credible agency sales demo: a prospect can inspect
an invoice, understand a discrepancy, record a decision, and see the preserved
evidence. Reliability and clear decisions take priority over feature count.

This file preserves responsibilities, decisions, and acceptance criteria between
working sessions. Agents are temporary collaborators, not continuously running
services. The repository and verification reports are the durable handoff.

## Responsibilities

| Role | Responsibility and handoff |
| --- | --- |
| Product manager | Turn observed problems into a small ranked scope; agree acceptance with engineering and design before implementation; reject additions without a user benefit. |
| Core engineering | Reproduce defects, implement typed changes at the right layer, preserve data contracts and history, and provide regression evidence. |
| Security review | Check authorization, isolation, resource bounds, safe failures and dependencies. Distinguish verified controls from untested assumptions. This may be a separate agent or an explicit engineering review assignment. |
| Design and QA | Check the complete prospect journey, accessible recovery states, precise copy and responsive behavior; independently verify the visible result. |
| Privacy and claims review | Verify retention, fixture, confidence and licensing language against implementation and sources. Flag unresolved decisions without claiming legal certification or selecting a license for the owner. |
| Release lead | Reconcile shared edits, run integrated checks, review test evidence, publish within authorization, and verify the deployed version. |

The PM coordinates directly with engineering and design; findings do not wait for
a chain of approvals. Each change has a user problem, evidence, owner, and pass
condition. Engineering and design exchange API/UI assumptions before changing
behavior. The release lead resolves conflicts and records final verification.
No role may substitute a claim of quality for a measured check.

## Accepted follow-up scope

These two issues were independently reviewed by PM, core engineering, and
design/QA after the completed [November release](REVIEW_2026_11.md).

### 1. Keep sample exploration usable

**Problem:** Guest workspaces start with four samples. Sample-card clicks create
new jobs, and the eight-sample cap then permanently rejects more selections.
The reproduced sequence was four successful additional selections followed by
HTTP 429. A returning prospect can lose the obvious path into the demo.

**Decision:** Guest sample cards open the canonical existing example in their
own workspace. Reopening retains its original extraction and any review decision.
It does not reset the record or create another extraction. Operator sample runs
retain their existing behavior.

**Acceptance:** Repeated guest selections keep the job count stable, work even
for a legacy workspace at the old cap, preserve decisions/audits, never cross
workspace ownership, and make no provider call. Missing legacy sample records
have a safe, deterministic recovery. The UI says “Open sample” and explains that
existing reviews remain. Resetting a reviewed sample is separate future work.

### 2. Give an unavailable live workspace a useful exit

**Problem:** The connection card only offers retry and operator access. A guest
rejected by admission limits, or returning during an outage, cannot discover the
already-available static sample preview from that screen.

**Decision:** Add a fixed link to the public sample preview in relevant live
connection/admission failure states. Explain that it uses synthetic samples,
does not accept uploads, and does not persist work on the server.

**Acceptance:** New and returning guests can reach the preview from a failed
connection. The link forwards no credentials, document IDs, or query parameters.
The preview does not offer a link back to itself as recovery. Retry and operator
access continue working. No silent replacement of a live result with a fixture.

The engineering owner supplies focused regressions; design/QA checks wording,
keyboard navigation and the visible error path. The release lead records final
suite, build, browser and deployment results after they run. Baseline results do
not establish that these new changes passed.

## Ranked deferred work

1. **Live-demo continuity:** The current free database is recorded to expire on
   November 6, 2026. Resolve storage before extending live outreach; retain the
   static preview meanwhile. This follow-up does not introduce paid services.
2. **Real workflow evidence:** Evaluate authorized, non-sensitive invoices from
   one agency and measure extraction quality and reviewer effort. Synthetic
   samples establish workflow behavior, not accuracy on client documents.
3. **Correction feedback:** Align the API's validation-error shape with the
   frontend formatter so a rejected correction identifies the affected field.
   Reproduce the mismatch before implementation; it is outside this follow-up.
4. **Measured capacity:** Profile actual parser and queue load before increasing
   public limits, adding preview caching, or introducing multiple workers.
5. **Client delivery decisions:** Choose required identity, retention, provider
   terms and licensing before promising proprietary white-label reuse. Start an
   ERP-specific connector only with a concrete client contract.

Defer generic dashboards, billing, more providers, and a full organization system.
Keep guest access available under the existing policy, preserve labeled samples,
and continue deleting personal uploads through the existing retention path.
