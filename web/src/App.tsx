import { useCallback, useEffect, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  CheckCheck,
  ChevronRight,
  CircleHelp,
  FileCheck2,
  Files,
  Inbox,
  LogOut,
  Plus,
  ShieldCheck,
  Timer,
  X,
} from "lucide-react";
import { request } from "./api";
import { labels, type Job } from "./types";
import Intake from "./Intake";
import Document from "./Document";

export default function App() {
  const [token, setToken] = useState(
    sessionStorage.getItem("folio-token") ?? "",
  );
  const [tokenInput, setTokenInput] = useState("");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [view, setView] = useState<"all" | "review">("all");
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [provider, setProvider] = useState("fixture");
  const [ready, setReady] = useState(false);
  const load = useCallback(async () => {
    if (!token) return;
    try {
      const [items, config] = await Promise.all([
        request<Job[]>("/jobs", token),
        request<{ provider: string }>("/config", token),
      ]);
      setJobs(items);
      setProvider(config.provider);
      setReady(true);
    } catch (error) {
      setError((error as Error).message);
    }
  }, [token]);
  useEffect(() => {
    void load();
    const timer = setInterval(() => void load(), 1500);
    return () => clearInterval(timer);
  }, [load]);
  async function login(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    try {
      await request("/config", tokenInput);
      sessionStorage.setItem("folio-token", tokenInput);
      setToken(tokenInput);
    } catch (error) {
      setError((error as Error).message);
    }
  }
  const reviewCount = jobs.filter(
    (j) => j.status === "REQUIRES_HUMAN_REVIEW",
  ).length;
  const approved = jobs.filter((j) =>
    ["AUTO_APPROVED", "HUMAN_APPROVED"].includes(j.status),
  ).length;
  const filtered = jobs.filter(
    (j) =>
      (view === "all" || j.status === "REQUIRES_HUMAN_REVIEW") &&
      `${j.filename} ${j.summary?.vendor_name ?? ""}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  const current = jobs.find((j) => j.job_id === selected);
  if (!token)
    return (
      <div className="login">
        <form onSubmit={login}>
          <div className="eyebrow">Folio / Document verification</div>
          <h1 style={{ marginTop: 12 }}>
            A little more
            <br />
            certainty.
          </h1>
          <p>
            A workspace for turning invoices into verified records—with a human
            in control.
          </p>
          <label htmlFor="token">Operator access token</label>
          <input
            id="token"
            type="password"
            autoComplete="current-password"
            value={tokenInput}
            onChange={(e) => setTokenInput(e.target.value)}
            required
          />
          {error && <p role="alert">{error}</p>}
          <button className="primary" type="submit">
            Open workspace
            <ArrowRight size={16} />
          </button>
          <small>
            Local demo token: <code>local-demo-only</code>
            <br />
            Use your configured token for a shared installation.
          </small>
        </form>
      </div>
    );
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">f</span>folio
          <span
            style={{
              fontSize: 10,
              color: "#9aac9e",
              alignSelf: "end",
              marginBottom: 5,
            }}
          >
            {" "}
            /{" "}
          </span>
        </div>
        <div className="workspace-label">OPERATIONS WORKSPACE</div>
        <nav className="nav">
          <button
            className={view === "all" ? "active" : ""}
            onClick={() => {
              setView("all");
              setSelected(null);
            }}
          >
            <Files size={17} />
            Documents
          </button>
          <button
            className={view === "review" ? "active" : ""}
            onClick={() => {
              setView("review");
              setSelected(null);
            }}
          >
            <Inbox size={17} />
            Review queue<span className="nav-count">{reviewCount}</span>
          </button>
        </nav>
        <div className="sidebar-bottom">
          <ShieldCheck size={23} style={{ marginBottom: 10 }} />
          <strong>Trust is a workflow.</strong>Every decision has its evidence.
          <br />
          Every correction leaves a trail.
          <a href="/docs" target="_blank" rel="noreferrer">
            API documentation
            <ArrowUpRight size={13} />
          </a>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div className="crumb">
            <span className="muted">Workspace</span>
            <ChevronRight size={12} />
            <span>
              {selected
                ? "Document review"
                : view === "review"
                  ? "Review queue"
                  : "Documents"}
            </span>
          </div>
          <div className="operator">
            <span className="mode-pill">
              <span className="dot" />
              {provider === "fixture" ? "SAMPLE WORKSPACE" : "LIVE WORKSPACE"}
            </span>
            <span className="avatar">OP</span>
            <button
              className="ghost"
              aria-label="Sign out"
              onClick={() => {
                sessionStorage.removeItem("folio-token");
                setToken("");
                setReady(false);
                setSelected(null);
                setJobs([]);
              }}
            >
              <LogOut size={15} />
            </button>
          </div>
        </header>
        <div className="content">
          {error && (
            <div className="error" role="alert">
              <span>{error}</span>
              <button
                className="ghost"
                aria-label="Dismiss error"
                onClick={() => setError("")}
              >
                <X size={14} />
              </button>
            </div>
          )}
          {current ? (
            <Document
              key={current.job_id}
              job={current}
              token={token}
              back={() => setSelected(null)}
              refresh={() => void load()}
              onError={setError}
            />
          ) : (
            <>
              <div className="heading">
                <div>
                  <div className="eyebrow">Less entry. More certainty.</div>
                  <h1>
                    {view === "review"
                      ? "A human makes the call."
                      : "From paperwork to proof."}
                  </h1>
                  <p>
                    {view === "review"
                      ? "The exceptions that deserve your attention."
                      : "A clear path from incoming invoices to records you can trust."}
                  </p>
                </div>
                <button
                  className="primary"
                  onClick={() => {
                    setView("all");
                    document
                      .getElementById("intake")
                      ?.scrollIntoView({ behavior: "smooth" });
                  }}
                >
                  <Plus size={15} />
                  New document
                </button>
              </div>
              <div className="metrics">
                <div className="metric">
                  <div className="metric-top">
                    Documents received
                    <Files size={16} />
                  </div>
                  <div className="metric-value">
                    {String(jobs.length).padStart(2, "0")}
                  </div>
                  <small>Latest 100 documents</small>
                </div>
                <div className="metric">
                  <div className="metric-top">
                    Approved records
                    <CheckCheck size={16} />
                  </div>
                  <div
                    className="metric-value"
                    style={{ color: "var(--green)" }}
                  >
                    {String(approved).padStart(2, "0")}
                  </div>
                  <small>Automatic + human decisions</small>
                </div>
                <div className="metric">
                  <div className="metric-top">
                    Awaiting review
                    <Timer size={16} />
                  </div>
                  <div
                    className="metric-value"
                    style={{ color: "var(--amber)" }}
                  >
                    {String(reviewCount).padStart(2, "0")}
                  </div>
                  <small>Held safely until resolved</small>
                </div>
              </div>
              {view === "all" && (
                <div id="intake">
                  <Intake
                    token={token}
                    provider={provider}
                    onError={setError}
                    onCreated={(job) => {
                      setJobs((items) => [job, ...items]);
                      setSelected(job.job_id);
                      setError("");
                    }}
                  />
                </div>
              )}
              <section className="panel">
                <div className="panel-head">
                  <div>
                    <h2>
                      {view === "review" ? "Review queue" : "Document register"}
                    </h2>
                    <p>
                      {view === "review"
                        ? "Resolve discrepancies and preserve the evidence."
                        : "Each document, its decision, and the path it took."}
                    </p>
                  </div>
                  <input
                    className="search"
                    aria-label="Search documents"
                    placeholder="Search documents…"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                  />
                </div>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Document</th>
                        <th>Amount</th>
                        <th>Decision</th>
                        <th>Received</th>
                        <th>
                          <span className="muted">Open</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((job) => (
                        <tr key={job.job_id}>
                          <td>
                            <div className="file-cell">
                              <FileCheck2 size={21} className="muted" />
                              <div>
                                <strong>
                                  {job.summary?.vendor_name ?? job.filename}
                                </strong>
                                <small>
                                  {job.summary?.invoice_number ?? job.filename}{" "}
                                  ·{" "}
                                  {job.mode === "fixture"
                                    ? "Sample"
                                    : `${job.page_count} pages`}
                                </small>
                              </div>
                            </div>
                          </td>
                          <td>
                            {job.summary?.total_amount ?? "—"}{" "}
                            <small className="muted">
                              {job.summary?.currency}
                            </small>
                          </td>
                          <td>
                            <span
                              className={`badge ${job.status === "REQUIRES_HUMAN_REVIEW" ? "review" : ["FAILED", "REJECTED"].includes(job.status) ? "failed" : ["QUEUED", "PROCESSING"].includes(job.status) ? "pending" : ""}`}
                            >
                              {labels[job.status]}
                            </span>
                          </td>
                          <td className="muted">
                            {new Date(job.created_at).toLocaleDateString(
                              undefined,
                              { month: "short", day: "numeric" },
                            )}
                          </td>
                          <td>
                            <button
                              className="ghost"
                              aria-label={`Open ${job.filename}`}
                              onClick={() => setSelected(job.job_id)}
                            >
                              <ArrowUpRight size={16} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {filtered.length === 0 && (
                    <div className="empty">
                      {!ready
                        ? "Connecting to your workspace…"
                        : query
                          ? "No matching documents."
                          : view === "review"
                            ? "All clear. No documents are waiting for review."
                            : "Your register starts here. Try a sample or upload your first invoice."}
                    </div>
                  )}
                </div>
                <div className="table-footer">
                  {filtered.length} documents · Original extractions are
                  preserved after review
                </div>
              </section>
            </>
          )}
          <footer className="footer">
            <span>
              <ShieldCheck size={12} />
              Extraction assisted by AI. Approval governed by checks.
            </span>
            <span>
              <CircleHelp size={12} />
              {provider === "fixture"
                ? "Samples are synthetic. No API charges."
                : "Live mode · provider usage applies."}
            </span>
          </footer>
        </div>
      </main>
    </div>
  );
}
