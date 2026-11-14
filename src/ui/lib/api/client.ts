import { API_BASE_PATH } from "@/lib/constants";
import type { ErrorBody, Json } from "@/lib/api/types";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Json;
  readonly requestId: string | null;

  constructor(status: number, body: ErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.details = body.details;
    this.requestId = body.request_id;
  }
}

export type QueryValue =
  string | number | boolean | null | undefined | readonly (string | number)[];
export type QueryParams = Record<string, QueryValue>;

export function buildQuery(params: QueryParams | undefined): string {
  if (!params) return "";
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((item) => search.append(key, String(item)));
    else search.append(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export async function toApiError(response: Response): Promise<ApiError> {
  try {
    const payload = (await response.json()) as { error?: ErrorBody };
    if (payload.error) return new ApiError(response.status, payload.error);
  } catch {
    // The body was not the error envelope; fall through to a generic error.
  }
  return new ApiError(response.status, {
    code: "internal_error",
    message: `Request failed with status ${response.status}`,
    details: null,
    request_id: response.headers.get("X-Request-ID"),
  });
}

async function request(path: string, init?: RequestInit): Promise<Response> {
  const response = await fetch(`${API_BASE_PATH}${path}`, init);
  if (!response.ok) throw await toApiError(response);
  return response;
}

export async function apiGet<T>(
  path: string,
  params?: QueryParams,
  signal?: AbortSignal,
): Promise<T> {
  const response = await request(`${path}${buildQuery(params)}`, { signal });
  return (await response.json()) as T;
}

export async function apiPost<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const response = await request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  return (await response.json()) as T;
}

export interface DownloadedFile {
  blob: Blob;
  filename: string;
}

const FILENAME_PATTERN = /filename="?([^";]+)"?/i;

export async function apiDownload(path: string, body: unknown): Promise<DownloadedFile> {
  const response = await request(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename = FILENAME_PATTERN.exec(disposition)?.[1] ?? "flamescope-export";
  return { blob: await response.blob(), filename };
}

export function saveFile({ blob, filename }: DownloadedFile): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
