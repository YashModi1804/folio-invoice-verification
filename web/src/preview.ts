import type { Audit, Check, Decision, Invoice, Job } from "./types";

export const PUBLIC_PREVIEW = import.meta.env.VITE_FOLIO_PUBLIC_PREVIEW === "true";

type Example = { kind: string; job: Job };
type PreviewState = {
  examples: Map<string, Job>;
  jobs: Job[];
  audits: Map<string, Audit[]>;
  decisions: Map<string, Decision>;
  kinds: Map<string, string>;
};

let previewState: Promise<PreviewState> | undefined;

function event(event: string, actor: string, details: Audit["details"] = {}): Audit {
  return { event, actor, details, created_at: new Date().toISOString() };
}

async function state(): Promise<PreviewState> {
  previewState ??= fetch(`${import.meta.env.BASE_URL}preview/data.json`)
    .then(async (response) => {
      if (!response.ok) throw new Error("Sample preview could not load.");
      return (await response.json()) as Example[];
    })
    .then((items) => {
      const examples = new Map(items.map(({ kind, job }) => [kind, job]));
      const jobs = items.map(({ job }, index) => ({
        ...structuredClone(job),
        created_at: new Date(Date.now() - index * 60_000).toISOString(),
      }));
      const audits = new Map(
        jobs.map((job) => [
          job.job_id,
          [
            event("UPLOADED", "Sample preview"),
            event("PROCESSING", "Sample preview"),
            event(job.status, "policy-v1"),
          ],
        ]),
      );
      const kinds = new Map(items.map(({ kind, job }) => [job.job_id, kind]));
      return { examples, jobs, audits, decisions: new Map(), kinds };
    });
  return previewState;
}

function findJob(store: PreviewState, jobId: string): Job {
  const job = store.jobs.find((item) => item.job_id === jobId);
  if (!job) throw new Error("Sample document not found.");
  return job;
}

export async function previewRequest<T>(path: string, options: RequestInit): Promise<T> {
  const store = await state();
  const method = options.method ?? "GET";
  if (path === "/config" && method === "GET")
    return {
      provider: "fixture",
      local_fallback_enabled: false,
      max_pages: 2,
    } as T;
  if (path === "/jobs" && method === "GET") return [...store.jobs] as T;
  if (path === "/documents" && method === "POST")
    throw new Error("This public preview accepts synthetic samples only. Private uploads require the hosted API.");

  const sample = path.match(/^\/samples\/(clean|variance|uncertain)$/);
  if (sample && method === "POST") {
    const kind = sample[1];
    const template = store.examples.get(kind);
    if (!template) throw new Error("Sample document not found.");
    const job = structuredClone(template);
    job.job_id = crypto.randomUUID();
    job.correlation_id = `synthetic-${job.job_id}`;
    job.created_at = new Date().toISOString();
    store.jobs.unshift(job);
    store.kinds.set(job.job_id, kind);
    store.audits.set(job.job_id, [
      event("UPLOADED", "Sample preview"),
      event("PROCESSING", "Sample preview"),
      event(job.status, "policy-v1"),
    ]);
    return job as T;
  }

  const audit = path.match(/^\/jobs\/([^/]+)\/audit$/);
  if (audit && method === "GET") return (store.audits.get(audit[1]) ?? []) as T;
  const decision = path.match(/^\/jobs\/([^/]+)\/decision$/);
  if (decision && method === "GET") return (store.decisions.get(decision[1]) ?? null) as T;
  const review = path.match(/^\/review-tasks\/([^/]+)\/decision$/);
  if (review && method === "POST") {
    const job = findJob(store, review[1]);
    if (job.status !== "REQUIRES_HUMAN_REVIEW")
      throw new Error("This sample is no longer waiting for review.");
    const body = JSON.parse(String(options.body)) as {
      action: "approve" | "reject";
      note: string;
      corrected_invoice: Invoice | null;
    };
    if (!body.note?.trim() || body.note.trim().length < 3)
      throw new Error("Add a short review note first.");
    if (body.corrected_invoice)
      throw new Error("Field corrections need the hosted API; this preview records decisions only.");
    job.status = body.action === "approve" ? "HUMAN_APPROVED" : "REJECTED";
    store.decisions.set(job.job_id, {
      action: body.action,
      note: body.note.trim(),
      actor: "Preview visitor",
      invoice: structuredClone(job.result!.invoice),
      checks: structuredClone(job.result!.checks) as Check[],
    });
    store.audits.get(job.job_id)?.push(event(job.status, "Preview visitor", {
      note: body.note.trim(),
      changes: {},
    }));
    return { status: job.status, correlation_id: job.correlation_id } as T;
  }
  throw new Error("This action needs the hosted API.");
}

export async function previewPageUrl(jobId: string, page: number): Promise<string> {
  const store = await state();
  const kind = store.kinds.get(jobId);
  if (!kind || page < 1 || page > 2) throw new Error("Sample page not found.");
  return `${import.meta.env.BASE_URL}preview/${kind}-${page}.png`;
}
