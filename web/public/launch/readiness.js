export const LIVE_ORIGIN = "https://folio-live-jutf.onrender.com";

// No credentials or invoice data cross from the static site to the readiness probe.
export async function probeWorkspace(fetcher = fetch, signal) {
  const response = await fetcher(`${LIVE_ORIGIN}/health/launch`, {
    credentials: "omit",
    cache: "no-store",
    redirect: "error",
    signal,
  });
  if (
    !response.ok ||
    !response.headers.get("content-type")?.includes("application/json")
  ) {
    return false;
  }
  const body = await response.json();
  return body.status === "ready";
}

export async function waitForWorkspace({
  signal,
  timeoutMs = 90_000,
  probe = probeWorkspace,
  clock = () => Date.now(),
  pause = (ms, abortSignal) =>
    new Promise((resolve) => {
      if (abortSignal.aborted) return resolve();
      const finish = () => {
        clearTimeout(timer);
        abortSignal.removeEventListener("abort", finish);
        resolve();
      };
      const timer = setTimeout(finish, ms);
      abortSignal.addEventListener("abort", finish, { once: true });
    }),
} = {}) {
  const deadline = clock() + timeoutMs;
  const cancelled = signal ?? new AbortController().signal;
  while (!cancelled.aborted && clock() < deadline) {
    const request = new AbortController();
    const cancelRequest = () => request.abort();
    cancelled.addEventListener("abort", cancelRequest, { once: true });
    const timer = setTimeout(
      cancelRequest,
      Math.max(1, Math.min(8_000, deadline - clock())),
    );
    try {
      if (await probe(undefined, request.signal)) return !cancelled.aborted;
    } catch {
      // Render's wake-up response lacks CORS headers. Retry until our API is ready.
    } finally {
      clearTimeout(timer);
      cancelled.removeEventListener("abort", cancelRequest);
    }
    if (!cancelled.aborted && clock() < deadline) {
      await pause(Math.min(3_000, deadline - clock()), cancelled);
    }
  }
  return false;
}
