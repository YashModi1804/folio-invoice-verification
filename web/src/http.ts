export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function parserErrorMessage(code: string): string | null {
  switch (code) {
    case "PARSER_BUSY":
      return "Document processing is busy. Please try again shortly.";
    case "PARSER_TIMEOUT":
      return "This document took too long to prepare. Try a smaller PDF or a clear image of the invoice.";
    case "PARSER_RESOURCE_LIMIT":
    case "PARSER_OUTPUT_LIMIT":
      return "This document exceeds the demo's processing limits. Try fewer pages or a lower-resolution copy.";
    case "PARSER_FAILED":
      return "This document could not be prepared safely. Try exporting a fresh PDF or uploading a clear image.";
    default:
      return null;
  }
}

function errorDetail(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return parserErrorMessage(detail) ?? detail;
  if (Array.isArray(detail)) {
    return detail
      .slice(0, 3)
      .map((item) => {
        const location = Array.isArray(item.loc)
          ? item.loc
              .filter(
                (part: unknown) =>
                  !["body", "corrected_invoice", "value"].includes(
                    String(part),
                  ),
              )
              .join(" ")
              .replaceAll("_", " ")
          : "Field";
        return `${location || "Field"}: ${typeof item.msg === "string" ? item.msg : "Check this value"}`;
      })
      .join(". ");
  }
  return status >= 500
    ? "The workspace is temporarily unavailable. Try again in a moment."
    : `Request failed (${status}). Please try again.`;
}

export async function fetchApi(
  url: string,
  token: string,
  options: RequestInit = {},
): Promise<Response> {
  const headers = new Headers(options.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const timeout = AbortSignal.timeout(30_000);
  const signal = options.signal
    ? AbortSignal.any([options.signal, timeout])
    : timeout;
  try {
    const response = await fetch(url, { ...options, headers, signal });
    if (!response.ok) {
      const body: unknown = await response.json().catch(() => null);
      throw new ApiError(response.status, errorDetail(body, response.status));
    }
    return response;
  } catch (error) {
    if (timeout.aborted && !options.signal?.aborted) {
      throw new ApiError(
        0,
        "The workspace is taking longer to respond. It may be waking up; please try again.",
      );
    }
    if (error instanceof TypeError) {
      throw new ApiError(
        0,
        "Unable to reach the workspace. Check your connection and try again.",
      );
    }
    throw error;
  }
}

export async function requestJson<T>(
  url: string,
  token: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetchApi(url, token, options);
  if (!response.headers.get("content-type")?.includes("application/json")) {
    throw new ApiError(
      503,
      "The workspace is starting. Please try again in a moment.",
    );
  }
  return response.json();
}
