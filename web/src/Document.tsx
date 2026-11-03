import { useEffect, useState } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  ExternalLink,
  Loader2,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import { pageUrl, request } from "./api";
import { parserErrorMessage } from "./http";
import {
  humanize,
  labels,
  type Audit,
  type Check,
  type Decision,
  type Field,
  type Invoice,
  type Job,
} from "./types";
import Review from "./Review";
import { PUBLIC_PREVIEW } from "./preview";
import { fieldWasCorrected, validEvidence } from "./workspace";

const fieldNames = [
  "vendor_name",
  "vendor_tax_id",
  "invoice_number",
  "invoice_date",
  "currency",
  "subtotal",
  "tax_amount",
  "shipping_amount",
  "discount_amount",
  "total_amount",
] as const;

function describeRouteReason(
  reason: string,
  failedTotal?: Check,
  currency?: string | null,
) {
  if (reason === "TOTAL_FAIL" && failedTotal) {
    return `Printed total ${failedTotal.observed}; calculated total ${failedTotal.expected}. Difference: ${currency ?? ""} ${failedTotal.variance}.`;
  }
  if (reason === "INVALID_EVIDENCE_PAGE_REFERENCE") {
    return "One or more model citations point to a page that is not in this document.";
  }
  if (reason.startsWith("MISSING_")) {
    return `Required field not found: ${humanize(reason.slice(8))}.`;
  }
  return humanize(reason);
}

function reviewSummary(
  reasons: string[],
  failedTotal?: Check,
  currency?: string | null,
) {
  const summary: string[] = [];
  if (reasons.includes("TOTAL_FAIL") && failedTotal) {
    summary.push(describeRouteReason("TOTAL_FAIL", failedTotal, currency));
  }
  if (reasons.some((reason) => reason.endsWith("_NOT_APPLICABLE"))) {
    summary.push(
      "The document does not provide enough detail to reconcile all printed amounts.",
    );
  }
  const unstated = ["TAX_AMOUNT", "SHIPPING_AMOUNT", "DISCOUNT_AMOUNT"].filter(
    (field) => reasons.includes(`MISSING_${field}`),
  );
  if (unstated.length) {
    summary.push(
      `Not stated on the document: ${unstated.map(humanize).join(", ")}.`,
    );
  }
  const missingCore = reasons
    .filter((reason) => reason.startsWith("MISSING_"))
    .map((reason) => reason.slice(8))
    .filter(
      (field) =>
        !["TAX_AMOUNT", "SHIPPING_AMOUNT", "DISCOUNT_AMOUNT"].includes(field),
    );
  if (missingCore.length) {
    summary.push(
      `Required details need confirmation: ${missingCore.map(humanize).join(", ")}.`,
    );
  }
  if (reasons.includes("INVALID_EVIDENCE_PAGE_REFERENCE")) {
    summary.push(
      "Some source citations cannot be opened and need a quick check.",
    );
  }
  return summary.length
    ? summary
    : ["This record needs a human decision before approval."];
}

function traceValue(key: string, value: unknown): string {
  if (value === null || value === undefined) return "Not available";
  if (key === "page_plan" && typeof value === "object") {
    const plan = value as {
      selected_pages?: number[];
      skipped_pages?: number[];
    };
    const selected = plan.selected_pages?.join(", ") || "none";
    const skipped = plan.skipped_pages?.join(", ") || "none";
    return `Selected pages ${selected}; skipped pages ${skipped}`;
  }
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

export function CheckLedger({ checks }: { checks: Check[] }) {
  return (
    <section className="panel section-gap">
      <div className="panel-head">
        <div>
          <h2>Verification ledger</h2>
          <p>
            {PUBLIC_PREVIEW
              ? "Precomputed by Folio's Python decimal verifier"
              : "Calculated independently with decimal arithmetic"}
          </p>
        </div>
        <ShieldCheck size={19} />
      </div>
      {checks.map((check) => (
        <div className="check" key={check.code}>
          <div>
            <div className="check-title">
              {check.state === "PASS" ? (
                <CheckCircle2 size={14} className="pass-icon" />
              ) : (
                <TriangleAlert size={14} className="warn-icon" />
              )}
              <span style={{ textTransform: "capitalize" }}>
                {humanize(check.code)}
              </span>
            </div>
            <small>
              Expected {check.expected ?? "—"} · Observed{" "}
              {check.observed ?? "—"}
            </small>
          </div>
          <span className={`badge ${check.state === "PASS" ? "" : "review"}`}>
            {check.state === "PASS"
              ? "Passed"
              : check.state === "FAIL"
                ? `Δ ${check.variance}`
                : "Incomplete"}
          </span>
        </div>
      ))}
    </section>
  );
}

export default function Document({
  job,
  token,
  back,
  refresh,
  onError,
}: {
  job: Job;
  token: string;
  back: () => void;
  refresh: () => Promise<void>;
  onError: (message: string) => void;
}) {
  const [page, setPage] = useState(1);
  const [image, setImage] = useState("");
  const [imageError, setImageError] = useState("");
  const [sourceAttempt, setSourceAttempt] = useState(0);
  const [evidence, setEvidence] = useState("");
  const [originalCitation, setOriginalCitation] = useState(false);
  const [audit, setAudit] = useState<Audit[]>([]);
  const [decision, setDecision] = useState<Decision>(null);
  const [recordView, setRecordView] = useState<"reviewed" | "original">(
    "reviewed",
  );
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Invoice | null>(null);
  const pending = ["QUEUED", "PROCESSING"].includes(job.status);
  const waitingForCapacity =
    job.status === "QUEUED" &&
    job.not_before !== null &&
    Date.parse(job.not_before) > Date.now();
  const capacityWaitSeconds = job.not_before
    ? Math.max(0, Math.ceil((Date.parse(job.not_before) - Date.now()) / 1000))
    : 0;
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    if (!pending) return;
    const update = () =>
      setElapsed(
        Math.max(
          0,
          Math.floor((Date.now() - Date.parse(job.created_at)) / 1000),
        ),
      );
    update();
    const timer = setInterval(update, 1000);
    return () => clearInterval(timer);
  }, [job.created_at, pending]);
  useEffect(() => {
    if (!pending) return;
    let active = true;
    const timer = setInterval(() => {
      request<Audit[]>(`/jobs/${job.job_id}/audit`, token)
        .then((events) => {
          if (active) setAudit(events);
        })
        .catch(() => {}); // Main job polling reports connection failures.
    }, 2000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [job.job_id, pending, token]);
  useEffect(() => {
    let active = true;
    let url = "";
    const controller = new AbortController();
    setImage("");
    setImageError("");
    pageUrl(job.job_id, page, token, controller.signal)
      .then((value) => {
        url = value;
        if (active) setImage(value);
        else if (value.startsWith("blob:")) URL.revokeObjectURL(value);
      })
      .catch((error) => {
        if (active) setImageError(error.message);
      });
    return () => {
      active = false;
      controller.abort();
      if (url.startsWith("blob:")) URL.revokeObjectURL(url);
    };
  }, [job.job_id, page, token, sourceAttempt]);
  useEffect(() => {
    let active = true;
    Promise.all([
      request<Audit[]>(`/jobs/${job.job_id}/audit`, token),
      request<Decision>(`/jobs/${job.job_id}/decision`, token),
    ])
      .then(([events, item]) => {
        if (active) {
          setAudit(events);
          setDecision(item);
        }
      })
      .catch((error) => {
        if (active) onError(error.message);
      });
    return () => {
      active = false;
    };
  }, [job.job_id, job.status, token]);
  const recovering =
    pending && audit.some((event) => event.event === "LOCAL_FALLBACK_STARTED");
  const review = job.status === "REQUIRES_HUMAN_REVIEW";
  const failedTotal = job.result?.checks.find(
    (check) => check.code === "TOTAL" && check.state === "FAIL",
  );
  const failed = ["FAILED", "REJECTED"].includes(job.status);
  const showOriginal = Boolean(decision && recordView === "original");
  const invoice = editing
    ? draft
    : showOriginal
      ? job.result?.invoice
      : (decision?.invoice ?? job.result?.invoice);
  function showEvidence(field: Field, fromReview = false) {
    const source = validEvidence(field, job.page_count);
    if (source) {
      setPage(source.page_number);
      setEvidence(source.text);
      setOriginalCitation(fromReview);
    }
  }
  function navigatePage(next: number) {
    setPage(Math.min(job.page_count, Math.max(1, next)));
    setEvidence("");
  }
  function updateLine(
    index: number,
    key: keyof Invoice["line_items"][number],
    value: string,
  ) {
    if (!draft) return;
    setDraft({
      ...draft,
      line_items: draft.line_items.map((line, i) =>
        i === index
          ? { ...line, [key]: key === "description" ? value : value || null }
          : line,
      ),
    });
  }
  return (
    <>
      <button className="ghost back" onClick={back}>
        <ArrowLeft size={15} />
        Back to documents
      </button>
      <div className="heading">
        <div>
          <div className="eyebrow">Document workspace</div>
          <h1>
            {invoice?.vendor_name.value ??
              job.summary?.vendor_name ??
              (pending ? "Reading your document" : job.filename)}
          </h1>
          <p>
            {job.filename} · {job.page_count} pages ·{" "}
            {job.mode === "fixture"
              ? "Synthetic sample"
              : job.mode === "ollama"
                ? "Local AI extraction"
                : `${job.mode === "groq" ? "Groq" : "Gemini"} live extraction`}
          </p>
        </div>
        <span className="mode-pill">
          {job.mode === "fixture"
            ? "FIXTURE MODE"
            : job.mode === "ollama"
              ? "LOCAL AI"
              : `${job.mode.toUpperCase()} LIVE`}
        </span>
      </div>
      {job.result?.telemetry.fallback_reason && (
        <p className="evidence" role="status">
          Completed with local AI after{" "}
          {job.requested_provider === "groq" ? "Groq" : "Gemini"} was
          unavailable. The original cloud failure is recorded in the audit
          trail; verification rules are unchanged.
        </p>
      )}
      <div
        className={`decision-banner ${review ? "review" : failed ? "failed" : ""}`}
        role="status"
      >
        {pending ? (
          <Loader2 className="spin" size={21} />
        ) : review || failed ? (
          <TriangleAlert size={21} />
        ) : (
          <ShieldCheck size={21} />
        )}
        <div>
          <h3>{labels[job.status]}</h3>
          <p>
            {pending
              ? recovering
                ? `Cloud service unavailable. Local AI is processing this document · ${elapsed}s elapsed.`
                : waitingForCapacity
                  ? `Waiting for provider capacity. Next attempt in about ${capacityWaitSeconds}s; no model request has been made yet.`
                  : `Extracting and independently verifying your document · ${elapsed}s elapsed.`
              : review
                ? "This record is held for review. Resolve the flagged details before approval."
                : failed
                  ? job.error === "PROVIDER_RATE_LIMITED"
                    ? "The provider's request quota is exhausted. Retry after it resets. No financial record was approved."
                    : job.error === "PROVIDER_CAPACITY_CONFIGURATION"
                      ? "This document needs more provider capacity than this demo can reserve. Try a smaller document or contact the workspace owner. No extraction request was sent."
                      : (parserErrorMessage(job.error ?? "") ??
                        humanize(job.error ?? "Record rejected by reviewer"))
                  : "The record is approved. Its original extraction and verification history are preserved."}
          </p>
          {pending && (
            <div className="stepper">
              <span className="done">1 Uploaded</span>
              <span className={job.status === "PROCESSING" ? "done" : ""}>
                2 Extracting
              </span>
              <span>3 Verify</span>
              <span>4 Route</span>
            </div>
          )}
          {review && (
            <>
              <ul className="reason-list">
                {reviewSummary(
                  job.result?.route_reasons ?? [],
                  failedTotal,
                  job.result?.invoice.currency.value,
                ).map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
              <details className="review-trace">
                <summary>
                  Technical review trace (
                  {job.result?.route_reasons.length ?? 0} checks)
                </summary>
                <ul className="reason-list">
                  {job.result?.route_reasons.map((reason) => (
                    <li key={reason}>
                      {describeRouteReason(
                        reason,
                        failedTotal,
                        job.result?.invoice.currency.value,
                      )}
                    </li>
                  ))}
                </ul>
              </details>
            </>
          )}
        </div>
      </div>
      <div className="document-grid">
        <div>
          <section className="panel">
            <div className="source-toolbar">
              <strong>Source document</strong>
              <div className="toolbar">
                <button
                  aria-label="Previous page"
                  disabled={page <= 1}
                  onClick={() => navigatePage(page - 1)}
                >
                  <ChevronLeft size={16} />
                </button>
                <span>
                  {page} / {job.page_count}
                </span>
                <button
                  aria-label="Next page"
                  disabled={page >= job.page_count}
                  onClick={() => navigatePage(page + 1)}
                >
                  <ChevronRight size={16} />
                </button>
                {image && (
                  <a
                    className="source-expand"
                    href={image}
                    target="_blank"
                    rel="noreferrer"
                    aria-label={`Open source page ${page} at full size`}
                    title="Open full size"
                  >
                    <ExternalLink size={16} />
                  </a>
                )}
              </div>
            </div>
            {evidence && (
              <div className="evidence">
                <strong>
                  {originalCitation
                    ? "Original extraction citation:"
                    : job.mode === "fixture"
                      ? "Sample evidence:"
                      : "Model-cited evidence:"}
                </strong>{" "}
                “{evidence}”<br />
                <span className="muted">
                  {originalCitation
                    ? "This citation belongs to the original extraction. A reviewer may have corrected the displayed value."
                    : job.mode === "fixture"
                      ? "This citation is part of a synthetic fixture, not a live extraction."
                      : "Check against the source page; citations are not independently verified."}
                </span>
              </div>
            )}
            <div className="source-stage">
              {image ? (
                <img src={image} alt={`Original invoice, page ${page}`} />
              ) : (
                <div className="source-message" role="status">
                  <p className="muted">
                    {imageError || "Loading source page…"}
                  </p>
                  {imageError && (
                    <button
                      onClick={() => setSourceAttempt((attempt) => attempt + 1)}
                    >
                      Retry source page
                    </button>
                  )}
                </div>
              )}
            </div>
          </section>
          <section className="panel section-gap">
            <div className="panel-head">
              <h2>Audit trail</h2>
              <Clock3 size={17} />
            </div>
            <div className="audit">
              {audit.map((event, index) => (
                <div className="audit-item" key={index}>
                  <strong>
                    {labels[event.event] ?? humanize(event.event)}
                  </strong>
                  <p>
                    {event.actor} ·{" "}
                    {new Date(event.created_at).toLocaleString()}
                  </p>
                  {event.details.note && <p>{event.details.note}</p>}
                  {event.details.changes && (
                    <p>
                      Updated:{" "}
                      {Object.keys(event.details.changes)
                        .map(humanize)
                        .join(", ") || "No field changes"}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </section>
        </div>
        <div>
          {invoice && (
            <section className="panel">
              <div className="panel-head">
                <div>
                  <h2>
                    {editing
                      ? "Correct extracted fields"
                      : showOriginal
                        ? "Original extraction"
                        : decision
                          ? "Reviewed record"
                          : PUBLIC_PREVIEW
                            ? "Sample details"
                            : "Extracted details"}
                  </h2>
                  <p>
                    {editing
                      ? "Checks below show the original extraction until you save."
                      : showOriginal
                        ? "Preserved exactly as extracted, before the review decision"
                        : decision
                          ? PUBLIC_PREVIEW
                            ? "Preview decision in this tab · original sample retained"
                            : "Human decision recorded · original retained"
                          : "Select a confidence label to inspect source evidence"}
                  </p>
                </div>
                {review && !PUBLIC_PREVIEW && (
                  <button
                    onClick={() => {
                      setDraft(structuredClone(job.result!.invoice));
                      setEditing(!editing);
                    }}
                  >
                    {editing ? "Cancel edit" : "Edit fields"}
                  </button>
                )}
              </div>
              {decision && (
                <div
                  className="record-switch"
                  role="group"
                  aria-label="Record version"
                >
                  <button
                    aria-pressed={!showOriginal}
                    onClick={() => setRecordView("reviewed")}
                  >
                    Reviewed record
                  </button>
                  <button
                    aria-pressed={showOriginal}
                    onClick={() => setRecordView("original")}
                  >
                    Original extraction
                  </button>
                </div>
              )}
              <div className="fields">
                {fieldNames.map((name) => {
                  const reviewedView = Boolean(decision && !showOriginal);
                  const sourceField = job.result!.invoice[name];
                  const corrected =
                    reviewedView &&
                    fieldWasCorrected(sourceField, invoice[name]);
                  return (
                    <div className="field" key={name}>
                      <span className="field-label">{humanize(name)}</span>
                      <div className="field-value">
                        {editing ? (
                          <input
                            aria-label={humanize(name)}
                            type={name === "invoice_date" ? "date" : "text"}
                            inputMode={
                              name.endsWith("amount") || name === "subtotal"
                                ? "decimal"
                                : undefined
                            }
                            value={invoice[name].value ?? ""}
                            onChange={(event) =>
                              setDraft({
                                ...invoice,
                                [name]: {
                                  ...invoice[name],
                                  value: event.target.value || null,
                                },
                              })
                            }
                          />
                        ) : (
                          <>
                            <strong>
                              {invoice[name].value ?? "Not found"}
                            </strong>
                            {corrected && (
                              <span className="reviewed-field">Reviewed</span>
                            )}
                            <button
                              onClick={() =>
                                showEvidence(sourceField, reviewedView)
                              }
                              disabled={
                                !validEvidence(sourceField, job.page_count)
                              }
                              title={
                                validEvidence(sourceField, job.page_count)
                                  ? reviewedView
                                    ? "View the original extraction citation; the reviewed value may differ"
                                    : "Model confidence, not calibrated probability"
                                  : "No source citation available for this field"
                              }
                              aria-label={`View ${reviewedView ? "original " : ""}${humanize(name)} source evidence`}
                            >
                              {!validEvidence(sourceField, job.page_count)
                                ? "No source"
                                : reviewedView
                                  ? "Original source"
                                  : invoice[name].value === null
                                    ? "Source"
                                    : `${Math.round(invoice[name].confidence * 100)}%`}
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Line item</th>
                      <th>Qty</th>
                      <th>Rate</th>
                      <th>Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {invoice.line_items.map((line, index) => (
                      <tr key={index}>
                        {(
                          [
                            "description",
                            "quantity",
                            "unit_price",
                            "line_total",
                          ] as const
                        ).map((key) => (
                          <td key={key}>
                            {editing ? (
                              <input
                                className="line-input"
                                aria-label={`Line ${index + 1} ${humanize(key)}`}
                                inputMode={
                                  key === "description" ? undefined : "decimal"
                                }
                                value={line[key] ?? ""}
                                onChange={(e) =>
                                  updateLine(index, key, e.target.value)
                                }
                              />
                            ) : (
                              (line[key] ?? "—")
                            )}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
          {job.result && (
            <CheckLedger
              checks={
                showOriginal
                  ? job.result.checks
                  : (decision?.checks ?? job.result.checks)
              }
            />
          )}
          {review && (
            <Review
              job={job}
              token={token}
              draft={editing ? draft : null}
              onDone={async () => {
                setEditing(false);
                await refresh();
              }}
            />
          )}
          {decision && (
            <section className="panel section-gap">
              <div className="panel-head">
                <div>
                  <h2>Review decision</h2>
                  <p>
                    {decision.actor}: {decision.note}
                  </p>
                </div>
              </div>
            </section>
          )}
          {job.result && (
            <section className="panel section-gap">
              <div className="panel-head">
                <h2>Processing trace</h2>
                <span className="eyebrow">For engineers</span>
              </div>
              <dl className="trace">
                {Object.entries(job.result.telemetry).map(([key, value]) => (
                  <div key={key}>
                    <dt>{humanize(key)}</dt>
                    <dd>{traceValue(key, value)}</dd>
                  </div>
                ))}
                <div className="wide">
                  <dt>Correlation ID</dt>
                  <dd>{job.correlation_id}</dd>
                </div>
              </dl>
            </section>
          )}
        </div>
      </div>
    </>
  );
}
