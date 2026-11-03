import type { Field, Job } from "./types";

/** Keep a slow poll or a previous workspace from replacing newer UI state. */
export class RequestScope {
  private current: AbortController | null = null;

  start(replace = false): AbortController | null {
    if (this.current && !replace) return null;
    this.cancel();
    this.current = new AbortController();
    return this.current;
  }

  owns(controller: AbortController): boolean {
    return this.current === controller && !controller.signal.aborted;
  }

  finish(controller: AbortController): void {
    if (this.current === controller) this.current = null;
  }

  cancel(): void {
    this.current?.abort();
    this.current = null;
  }
}

export function matchesDocument(job: Job, query: string): boolean {
  return [job.filename, job.summary?.vendor_name, job.summary?.invoice_number]
    .filter(Boolean)
    .join(" ")
    .toLowerCase()
    .includes(query.trim().toLowerCase());
}

export function validEvidence(field: Field, pageCount: number) {
  return field.evidence.find(
    (item) =>
      Number.isInteger(item.page_number) &&
      item.page_number >= 1 &&
      item.page_number <= pageCount,
  );
}

export function fieldWasCorrected(original: Field, reviewed: Field): boolean {
  return original.value !== reviewed.value;
}

export function prioritizeReviews(jobs: Job[]): Job[] {
  const failures = (job: Job) =>
    job.result?.checks.filter((check) => check.state === "FAIL").length ?? 0;
  return jobs
    .filter((job) => job.status === "REQUIRES_HUMAN_REVIEW")
    .sort(
      (a, b) =>
        failures(b) - failures(a) ||
        Date.parse(a.created_at) - Date.parse(b.created_at),
    );
}
