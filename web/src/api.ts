import { PUBLIC_PREVIEW, previewPageUrl, previewRequest } from "./preview";
import { fetchApi, requestJson } from "./http";
export { ApiError } from "./http";

export async function request<T>(
  path: string,
  token: string,
  options: RequestInit = {},
): Promise<T> {
  if (PUBLIC_PREVIEW) return previewRequest<T>(path, options);
  return requestJson<T>(`/api/v1${path}`, token, options);
}

export async function pageUrl(
  job: string,
  page: number,
  token: string,
  signal?: AbortSignal,
) {
  if (PUBLIC_PREVIEW) return previewPageUrl(job, page);
  const response = await fetchApi(`/api/v1/jobs/${job}/pages/${page}`, token, {
    signal,
  });
  return URL.createObjectURL(await response.blob());
}
