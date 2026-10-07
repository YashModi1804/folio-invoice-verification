import { PUBLIC_PREVIEW, previewPageUrl, previewRequest } from "./preview";

export async function request<T>(
  path: string,
  token: string,
  options: RequestInit = {},
): Promise<T> {
  if (PUBLIC_PREVIEW) return previewRequest<T>(path, options);
  const headers = new Headers(options.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const response = await fetch(`/api/v1${path}`, { ...options, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : `Request failed (${response.status})`,
    );
  }
  return response.json();
}

export async function pageUrl(job: string, page: number, token: string) {
  if (PUBLIC_PREVIEW) return previewPageUrl(job, page);
  const response = await fetch(`/api/v1/jobs/${job}/pages/${page}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok)
    throw new Error(
      "Source page is unavailable or its retention period has ended.",
    );
  return URL.createObjectURL(await response.blob());
}
