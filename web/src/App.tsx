import { useCallback, useEffect, useRef, useState } from "react";
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
import { ApiError, request } from "./api";
import { labels, type Job } from "./types";
import Intake from "./Intake";
import Document from "./Document";
import { PUBLIC_PREVIEW } from "./preview";
import { matchesDocument, RequestScope } from "./workspace";

export default function App() {
  const [token, setToken] = useState(
    PUBLIC_PREVIEW
      ? "public-preview"
      : (sessionStorage.getItem("folio-token") ??
          localStorage.getItem("folio-guest-token") ??
          ""),
  );
  const [tokenInput, setTokenInput] = useState("");
  const [workspace, setWorkspace] = useState<"operator" | "guest">(
    !PUBLIC_PREVIEW &&
      !sessionStorage.getItem("folio-token") &&
      localStorage.getItem("folio-guest-token")
      ? "guest"
      : "operator",
  );
  const [operatorLogin, setOperatorLogin] = useState(false);
  const [guestStarting, setGuestStarting] = useState(!PUBLIC_PREVIEW && !token);
  const [guestError, setGuestError] = useState("");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [reviewJobs, setReviewJobs] = useState<Job[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [selectedSnapshot, setSelectedSnapshot] = useState<Job | null>(null);
  const selectedRef = useRef(selected);
  selectedRef.current = selected;
  const [view, setView] = useState<"all" | "review">("all");
  const [error, setError] = useState("");
  const [loadError, setLoadError] = useState("");
  const [query, setQuery] = useState("");
  const [provider, setProvider] = useState("fixture");
  const [fallback, setFallback] = useState(false);
  const [maxPages, setMaxPages] = useState(20);
  const [maxFileMb, setMaxFileMb] = useState(20);
  const [temporaryDemo, setTemporaryDemo] = useState(false);
  const [ready, setReady] = useState(false);
  const loads = useRef(new RequestScope());
  const tokenRef = useRef(token);
  tokenRef.current = token;
  const guestRequest = useRef<Promise<void> | null>(null);
  const loginRequest = useRef(new RequestScope());
  const workspaceRef = useRef(workspace);
  workspaceRef.current = workspace;

  function resetWorkspace() {
    tokenRef.current = "";
    loads.current.cancel();
    setJobs([]);
    setReviewJobs([]);
    setSelected(null);
    setSelectedSnapshot(null);
    setReady(false);
    setQuery("");
    setView("all");
    setError("");
    setLoadError("");
  }

  function openJob(job: Job) {
    selectedRef.current = job.job_id;
    setSelectedSnapshot(job);
    setSelected(job.job_id);
  }

  const startGuest = useCallback(async () => {
    if (guestRequest.current) return guestRequest.current;
    setGuestStarting(true);
    setGuestError("");
    setOperatorLogin(false);
    loginRequest.current.cancel();
    guestRequest.current = (async () => {
      try {
        const saved = localStorage.getItem("folio-guest-token");
        const session = await (saved
          ? Promise.resolve({ token: saved })
          : request<{ token: string }>("/guest-sessions", "", {
              method: "POST",
            }));
        localStorage.setItem("folio-guest-token", session.token);
        setWorkspace("guest");
        setToken(session.token);
        setError("");
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          setOperatorLogin(true);
        } else {
          setGuestError((error as Error).message);
        }
      } finally {
        setGuestStarting(false);
        guestRequest.current = null;
      }
    })();
    return guestRequest.current;
  }, []);
  useEffect(() => {
    if (!PUBLIC_PREVIEW && !token && !operatorLogin && !guestError)
      void startGuest();
  }, [token, operatorLogin, guestError, startGuest]);
  const load = useCallback(
    async (replace = false) => {
      if (!token || tokenRef.current !== token) return;
      const controller = loads.current.start(replace);
      if (!controller) return;
      const options = { signal: controller.signal };
      try {
        const [items, reviews, config] = await Promise.all([
          request<Job[]>("/jobs", token, options),
          request<Job[]>("/review-tasks", token, options),
          request<{
            provider: string;
            local_fallback_enabled: boolean;
            max_pages: number;
            max_file_mb: number;
            workspace?: "operator" | "guest";
            temporary_demo?: boolean;
          }>("/config", token, options),
        ]);
        const selectedId = selectedRef.current;
        let snapshot: Job | null = null;
        if (
          selectedId &&
          !items.some((item) => item.job_id === selectedId) &&
          !reviews.some((item) => item.job_id === selectedId)
        ) {
          try {
            snapshot = await request<Job>(
              `/jobs/${selectedId}`,
              token,
              options,
            );
          } catch (error) {
            if (!(error instanceof ApiError && error.status === 404))
              throw error;
          }
        }
        if (!loads.current.owns(controller) || tokenRef.current !== token)
          return;
        if (selectedRef.current === selectedId) {
          setSelectedSnapshot(snapshot);
          if (
            selectedId &&
            !snapshot &&
            !items.some((item) => item.job_id === selectedId) &&
            !reviews.some((item) => item.job_id === selectedId)
          ) {
            setSelected(null);
            setError("This document is no longer available in your workspace.");
          }
        }
        setJobs(items);
        setReviewJobs(reviews);
        setProvider(config.provider);
        setWorkspace(config.workspace ?? "operator");
        setFallback(config.local_fallback_enabled);
        setMaxPages(config.max_pages);
        setMaxFileMb(config.max_file_mb ?? 20);
        setTemporaryDemo(Boolean(config.temporary_demo));
        setReady(true);
        setLoadError("");
      } catch (error) {
        if (!loads.current.owns(controller) || tokenRef.current !== token)
          return;
        if (error instanceof ApiError && error.status === 401) {
          if (workspaceRef.current === "guest")
            localStorage.removeItem("folio-guest-token");
          else {
            sessionStorage.removeItem("folio-token");
            setOperatorLogin(true);
          }
          setToken("");
          setJobs([]);
          setReviewJobs([]);
          setSelected(null);
          setSelectedSnapshot(null);
          setReady(false);
        } else {
          setLoadError((error as Error).message);
        }
      } finally {
        loads.current.finish(controller);
      }
    },
    [token],
  );
  useEffect(() => {
    void load();
    return () => loads.current.cancel();
  }, [load]);
  const hasPendingJob = jobs.some((job) =>
    ["QUEUED", "PROCESSING"].includes(job.status),
  );
  useEffect(() => {
    const refreshVisible = () => {
      if (!document.hidden) void load();
    };
    const timer = setInterval(refreshVisible, hasPendingJob ? 1500 : 15000);
    document.addEventListener("visibilitychange", refreshVisible);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", refreshVisible);
    };
  }, [load, hasPendingJob]);
  async function login(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    const controller = loginRequest.current.start();
    if (!controller) return;
    const submittedToken = tokenInput.trim();
    try {
      await request("/config", submittedToken, { signal: controller.signal });
      if (!loginRequest.current.owns(controller)) return;
      resetWorkspace();
      sessionStorage.setItem("folio-token", submittedToken);
      setWorkspace("operator");
      setToken(submittedToken);
      setTokenInput("");
    } catch (error) {
      if (loginRequest.current.owns(controller))
        setError((error as Error).message);
    } finally {
      loginRequest.current.finish(controller);
    }
  }
  const reviewCount = reviewJobs.length;
  const approved = jobs.filter((j) =>
    ["AUTO_APPROVED", "HUMAN_APPROVED"].includes(j.status),
  ).length;
  const filtered = (view === "all" ? jobs : reviewJobs).filter((job) =>
    matchesDocument(job, query),
  );
  const current =
    jobs.find((j) => j.job_id === selected) ??
    reviewJobs.find((j) => j.job_id === selected) ??
    (selectedSnapshot?.job_id === selected ? selectedSnapshot : undefined);
  if ((!token && !operatorLogin) || (token && !ready)) {
    const connectionError = guestError || loadError || error;
    return (
      <div className="login">
        <section className="connection-card" aria-live="polite">
          <div className="eyebrow">Folio / Document verification</div>
          <h1>
            {connectionError ? "Let's reconnect." : "Opening your workspace."}
          </h1>
          <p>
            {connectionError ||
              "Loading your documents and review queue. A sleeping demo service may take a moment to respond."}
          </p>
          {connectionError && (
            <button
              className="primary"
              onClick={() => {
                setError("");
                setLoadError("");
                if (token) void load(true);
                else void startGuest();
              }}
            >
              Try again
            </button>
          )}
          {!guestStarting && (
            <button
              className="ghost"
              onClick={() => {
                resetWorkspace();
                sessionStorage.removeItem("folio-token");
                setToken("");
                setOperatorLogin(true);
              }}
            >
              Operator access
            </button>
          )}
        </section>
      </div>
    );
  }
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
          <button
            className="ghost"
            type="button"
            onClick={() => void startGuest()}
          >
            Explore as guest
          </button>
          <small>
            Ask the workspace owner for an access token. Keep it private.
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
        <div className="workspace-label">
          {workspace === "guest"
            ? "PRIVATE DEMO WORKSPACE"
            : "OPERATIONS WORKSPACE"}
        </div>
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
          <a
            href={
              PUBLIC_PREVIEW
                ? "https://github.com/YashModi1804/folio-invoice-verification"
                : "/docs"
            }
            target="_blank"
            rel="noreferrer"
          >
            {PUBLIC_PREVIEW ? "View source code" : "API documentation"}
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
              {workspace === "guest"
                ? "PRIVATE GUEST DEMO"
                : provider === "fixture"
                  ? "SAMPLE WORKSPACE"
                  : provider === "ollama"
                    ? "LOCAL AI WORKSPACE"
                    : "LIVE WORKSPACE"}
            </span>
            <span className="avatar">
              {workspace === "guest" ? "GU" : "OP"}
            </span>
            {!PUBLIC_PREVIEW && (
              <button
                className="ghost"
                aria-label={
                  workspace === "guest" ? "Operator access" : "Sign out"
                }
                onClick={() => {
                  sessionStorage.removeItem("folio-token");
                  resetWorkspace();
                  setOperatorLogin(true);
                  setToken("");
                }}
              >
                <LogOut size={15} />
                {workspace === "guest" && "Operator access"}
              </button>
            )}
          </div>
        </header>
        <div className="content">
          {PUBLIC_PREVIEW && (
            <div className="preview-banner" role="status">
              <strong>Public sample preview</strong>
              <span>
                Synthetic invoices only · No live AI or server storage · Review
                decisions reset on refresh
              </span>
            </div>
          )}
          {(temporaryDemo || workspace === "guest") && !PUBLIC_PREVIEW && (
            <div className="preview-banner" role="status">
              <strong>
                {workspace === "guest"
                  ? "Private guest demo"
                  : "Temporary live demo"}
              </strong>
              <span>
                {workspace === "guest"
                  ? "Shared synthetic samples stay available · Private uploads and reviews auto-delete after two hours when the service is awake"
                  : "Real extraction and review · Source documents expire after seven days · Demo database expires after 30 days"}
              </span>
            </div>
          )}
          {(error || loadError) && (
            <div className="error" role="alert">
              <span>{error || loadError}</span>
              <button
                className="ghost"
                aria-label="Dismiss error"
                onClick={() => {
                  setError("");
                  setLoadError("");
                }}
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
              refresh={() => load(true)}
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
                    setQuery("");
                    requestAnimationFrame(() =>
                      document
                        .getElementById("intake")
                        ?.scrollIntoView({ behavior: "smooth" }),
                    );
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
                    publicPreview={PUBLIC_PREVIEW}
                    provider={provider}
                    fallback={fallback}
                    maxPages={maxPages}
                    maxFileMb={maxFileMb}
                    onError={setError}
                    onCreated={(job) => {
                      if (tokenRef.current !== token) return;
                      loads.current.cancel();
                      setJobs((items) => [
                        job,
                        ...items.filter((item) => item.job_id !== job.job_id),
                      ]);
                      if (job.status === "REQUIRES_HUMAN_REVIEW") {
                        setReviewJobs((items) => [
                          job,
                          ...items.filter((item) => item.job_id !== job.job_id),
                        ]);
                      }
                      openJob(job);
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
                        ? "Most discrepancies first, then oldest received."
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
                              onClick={() => openJob(job)}
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
                            : PUBLIC_PREVIEW
                              ? "Select a synthetic sample to explore the workflow."
                              : "Your register starts here. Try a sample or upload your first invoice."}
                      {query.trim() && (
                        <button className="ghost" onClick={() => setQuery("")}>
                          Clear search
                        </button>
                      )}
                    </div>
                  )}
                </div>
                <div className="table-footer">
                  {filtered.length}{" "}
                  {filtered.length === 1 ? "document" : "documents"} · Original
                  extractions are preserved after review
                </div>
              </section>
            </>
          )}
          <footer className="footer">
            <span>
              <ShieldCheck size={12} />
              {PUBLIC_PREVIEW
                ? "Synthetic examples · Real verification rules · No model call"
                : "Extraction assisted by AI. Approval governed by checks."}
            </span>
            <span>
              <CircleHelp size={12} />
              {provider === "fixture"
                ? "Samples are synthetic. No API charges."
                : provider === "ollama"
                  ? "Local inference · No API fees · Uses your hardware."
                  : "Live mode · provider usage applies."}
            </span>
          </footer>
        </div>
      </main>
    </div>
  );
}
