/** Thin fetch wrapper for the Django API: same-origin session cookie + CSRF header. */

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export type Query = Record<string, string | number | boolean | null | undefined>;

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(status: number, data: any) {
    super(errorText(data) || `Request failed (${status})`);
    this.status = status;
    this.data = data;
  }
}

function errorText(data: any): string {
  if (!data) return "";
  if (typeof data === "string") return data;
  if (data.detail) return String(data.detail);
  if (Array.isArray(data)) return data.map(errorText).join(" ");
  const first = Object.entries(data)[0];
  if (!first) return "";
  const [field, value] = first;
  const text = Array.isArray(value) ? value.join(" ") : typeof value === "object" ? errorText(value) : String(value);
  return field === "non_field_errors" ? text : `${field.replace(/_/g, " ")}: ${text}`;
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof TypeError) return "Cannot reach the server. Check your connection.";
  return error instanceof Error ? error.message : "Something went wrong.";
}

export function getCookie(name: string): string | null {
  const match = document.cookie.split("; ").find((row) => row.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.split("=")[1]) : null;
}

/** The school the owner console is setting up. While set, every request names it in the
 *  X-Setup-School header (file links in ?setup_school), and the server lets the platform
 *  team change that school's setup only. */
let setupSchool: number | null = null;

export function setSetupSchool(id: number | null) {
  setupSchool = id;
}

export function buildUrl(path: string, query?: Query): string {
  const url = new URL(`/api${path}`, window.location.origin);
  if (setupSchool) url.searchParams.set("setup_school", String(setupSchool));
  Object.entries(query ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, String(value));
  });
  return url.pathname + url.search;
}

interface Options {
  method?: string;
  body?: unknown;
  query?: Query;
  signal?: AbortSignal;
}

export async function api<T = any>(path: string, { method = "GET", body, query, signal }: Options = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (setupSchool) headers["X-Setup-School"] = String(setupSchool);
  let payload: BodyInit | undefined;
  if (body instanceof FormData) {
    payload = body;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  if (method !== "GET") {
    const token = getCookie("csrftoken");
    if (token) headers["X-CSRFToken"] = token;
  }
  const response = await fetch(buildUrl(path, query), {
    method,
    headers,
    body: payload,
    credentials: "same-origin",
    signal,
  });
  if (response.status === 204) return undefined as T;
  const type = response.headers.get("Content-Type") ?? "";
  const data = type.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) throw new ApiError(response.status, data);
  return data as T;
}

export const get = <T = any>(path: string, query?: Query) => api<T>(path, { query });
export const post = <T = any>(path: string, body?: unknown) => api<T>(path, { method: "POST", body: body ?? {} });
export const patch = <T = any>(path: string, body: unknown) => api<T>(path, { method: "PATCH", body });
export const del = (path: string) => api(path, { method: "DELETE" });

/** Open a PDF/Excel produced by the API in a new tab (the session cookie authorises it). */
export function openFile(path: string, query?: Query) {
  window.open(buildUrl(path, query), "_blank", "noopener");
}

export async function ensureCsrf() {
  if (!getCookie("csrftoken")) await get("/auth/csrf/");
}
