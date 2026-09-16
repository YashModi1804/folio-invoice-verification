import { useEffect, useState } from "react";
import {
  ArrowLeft,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Loader2,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import { pageUrl, request } from "./api";
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

export function CheckLedger({ checks }: { checks: Check[] }) {
  return (
    <section className="panel section-gap">
      <div className="panel-head">
        <div>
          <h2>Verification ledger</h2>
          <p>Calculated independently with decimal arithmetic</p>
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
  refresh: () => void;
  onError: (message: string) => void;
}) {
  const [page, setPage] = useState(1);
  const [image, setImage] = useState("");
  const [imageError, setImageError] = useState("");
  const [evidence, setEvidence] = useState("");
  const [audit, setAudit] = useState<Audit[]>([]);
  const [decision, setDecision] = useState<Decision>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<Invoice | null>(null);
  useEffect(() => {
    let active = true;
    let url = "";
    setImage("");
    setImageError("");
    pageUrl(job.job_id, page, token)
      .then((value) => {
        url = value;
        if (active) setImage(value);
        else URL.revokeObjectURL(value);
      })
      .catch((error) => {
        if (active) setImageError(error.message);
      });
    return () => {
      active = false;
      if (url) URL.revokeObjectURL(url);
    };
  }, [job.job_id, page, token]);
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
  const pending = ["QUEUED", "PROCESSING"].includes(job.status);
  const review = job.status === "REQUIRES_HUMAN_REVIEW";
  const failed = ["FAILED", "REJECTED"].includes(job.status);
  const invoice = editing ? draft : (decision?.invoice ?? job.result?.invoice);
  function showEvidence(field: Field) {
    const source = field.evidence[0];
    if (source) {
      setPage(source.page_number);
      setEvidence(source.text);
    }
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
        All documents
      </button>
      <div className="heading">
        <div>
          <div className="eyebrow">Document workspace</div>
          <h1>{job.summary?.vendor_name ?? "Reading your document"}</h1>
          <p>
            {job.filename} · {job.page_count} pages ·{" "}
            {job.mode === "fixture" ? "Synthetic sample" : "Live extraction"}
          </p>
        </div>
        <span className="mode-pill">
          {job.mode === "fixture" ? "FIXTURE MODE" : "LIVE MODE"}
        </span>
      </div>
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
              ? "Your document is queued for extraction and independent verification."
              : review
                ? "This record is held for review. Resolve the flagged details before approval."
                : failed
                  ? humanize(job.error ?? "Record rejected by reviewer")
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
            <ul className="reason-list">
              {job.result?.route_reasons.map((reason) => (
                <li key={reason}>• {humanize(reason)}</li>
              ))}
            </ul>
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
                  disabled={page === 1}
                  onClick={() => setPage(page - 1)}
                >
                  <ChevronLeft size={16} />
                </button>
                <span>
                  {page} / {job.page_count}
                </span>
                <button
                  aria-label="Next page"
                  disabled={page === job.page_count}
                  onClick={() => setPage(page + 1)}
                >
                  <ChevronRight size={16} />
                </button>
              </div>
            </div>
            {evidence && (
              <div className="evidence">
                <strong>Model-cited evidence:</strong> “{evidence}”<br />
                <span className="muted">
                  Check against the source page; citations are not independently
                  verified.
                </span>
              </div>
            )}
            <div className="source-stage">
              {image ? (
                <img src={image} alt={`Original invoice, page ${page}`} />
              ) : (
                <p className="muted">{imageError || "Loading source page…"}</p>
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
                      : decision
                        ? "Reviewed record"
                        : "Extracted details"}
                  </h2>
                  <p>
                    {editing
                      ? "Checks below show the original extraction until you save."
                      : decision
                        ? "Human decision recorded · original retained"
                        : "Select a confidence label to inspect source evidence"}
                  </p>
                </div>
                {review && (
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
              <div className="fields">
                {fieldNames.map((name) => (
                  <div className="field" key={name}>
                    <span className="field-label">{humanize(name)}</span>
                    <div className="field-value">
                      {editing ? (
                        <input
                          aria-label={humanize(name)}
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
                          <strong>{invoice[name].value ?? "Not found"}</strong>
                          <button
                            onClick={() => showEvidence(invoice[name])}
                            title="Model confidence, not calibrated probability"
                            aria-label={`View ${humanize(name)} source evidence`}
                          >
                            {Math.round(invoice[name].confidence * 100)}%
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                ))}
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
            <CheckLedger checks={decision?.checks ?? job.result.checks} />
          )}
          {review && (
            <Review
              job={job}
              token={token}
              draft={editing ? draft : null}
              onDone={() => {
                setEditing(false);
                refresh();
              }}
              onError={onError}
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
                    <dd>{value === null ? "Not available" : String(value)}</dd>
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
