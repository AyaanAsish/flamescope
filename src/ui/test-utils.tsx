/** Shared Vitest helpers: URL state, a query provider and a route-keyed fake of `lib/api/client`. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, type RenderResult } from "@testing-library/react";
import { useMemo, useSyncExternalStore, type ReactElement } from "react";
import { expect, vi } from "vitest";
import { ApiError, apiGet, apiPost } from "@/lib/api/client";

// --- next/navigation ---------------------------------------------------------------------

const urlState = { pathname: "/", search: "" };
const listeners = new Set<() => void>();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Points the mocked router at a URL such as `/ranking?lens=habitat`. */
export function setUrl(url: string): void {
  const [pathname = "/", search = ""] = url.split("?");
  urlState.pathname = pathname;
  urlState.search = search;
  listeners.forEach((listener) => listener());
}

export function currentSearch(): URLSearchParams {
  return new URLSearchParams(urlState.search);
}

export function resetNavigation(): void {
  setUrl("/");
}

const router = {
  push: vi.fn((url: string) => setUrl(url)),
  replace: vi.fn((url: string) => setUrl(url)),
  back: vi.fn(),
  forward: vi.fn(),
  refresh: vi.fn(),
  prefetch: vi.fn(),
};

function useSearchParams(): URLSearchParams {
  const search = useSyncExternalStore(subscribe, () => urlState.search);
  return useMemo(() => new URLSearchParams(search), [search]);
}

function usePathname(): string {
  return useSyncExternalStore(subscribe, () => urlState.pathname);
}

export const navigationMock = {
  useRouter: () => router,
  usePathname,
  useSearchParams,
  notFound: vi.fn(),
  redirect: vi.fn(),
};

// --- rendering ---------------------------------------------------------------------------

export function renderWithQuery(ui: ReactElement): RenderResult {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

// --- fake API (test files must `vi.mock("@/lib/api/client", ...)` first) ------------------

const PENDING_MARK = Symbol("pending");

/** A route answer that never settles, which keeps a panel in its loading state. */
export const PENDING = { [PENDING_MARK]: true } as const;

export type RouteAnswer = unknown;
/** Keys are `"GET /meta/stats"` or `"POST /rank"`; values are bodies, `PENDING` or an `ApiError`. */
export type ApiRoutes = Record<string, RouteAnswer>;

export function apiFailure(status = 500, message = "The API is unavailable"): ApiError {
  const code = status === 404 ? "not_found" : "internal_error";
  return new ApiError(status, { code, message, details: null, request_id: "req-test" });
}

function answer(routes: ApiRoutes, key: string): Promise<unknown> {
  if (!(key in routes)) return Promise.reject(apiFailure(404, `Unmocked route ${key}`));
  const value = routes[key];
  if (value === PENDING) return new Promise(() => undefined);
  if (value instanceof ApiError) return Promise.reject(value);
  return Promise.resolve(structuredClone(value));
}

/** Routes every `apiGet` / `apiPost` call of the mocked client to the given answers. */
export function serveApi(routes: ApiRoutes): void {
  vi.mocked(apiGet).mockImplementation((path: string) => answer(routes, `GET ${path}`) as never);
  vi.mocked(apiPost).mockImplementation((path: string) => answer(routes, `POST ${path}`) as never);
}

/** Every route answers with the same state, for loading and error checks. */
export function serveAll(keys: string[], value: RouteAnswer): ApiRoutes {
  return Object.fromEntries(keys.map((key) => [key, value]));
}

// --- state assertions --------------------------------------------------------------------

export function skeletonIn(element: Element): Element | null {
  return element.querySelector(".skeleton");
}

export function emptyStateIn(element: Element): Element | null {
  return element.querySelector('[data-state="empty"]');
}

export function errorStateIn(element: Element): Element | null {
  return element.querySelector('[data-state="error"]');
}

/** The four panel states of doc 10 section 2.3 rule 3 (data is "none of the others"). */
export type PanelState = "loading" | "empty" | "error" | "data";

const STATE_PROBES = { loading: skeletonIn, empty: emptyStateIn, error: errorStateIn } as const;

function stateOf(panel: Element): PanelState {
  if (errorStateIn(panel)) return "error";
  if (emptyStateIn(panel)) return "empty";
  return skeletonIn(panel) ? "loading" : "data";
}

type PanelLocator = string | (() => HTMLElement);

function locate(locator: PanelLocator): HTMLElement {
  return typeof locator === "string" ? screen.getByTestId(locator) : locator();
}

/** Waits until the panel (a `data-testid` or a getter) shows the given state, and returns it. */
export async function findPanelState(
  locator: PanelLocator,
  state: PanelState,
): Promise<HTMLElement> {
  return waitFor(() => {
    const panel = locate(locator);
    if (state !== "data") expect(STATE_PROBES[state](panel)).not.toBeNull();
    expect(stateOf(panel)).toBe(state);
    return panel;
  });
}
