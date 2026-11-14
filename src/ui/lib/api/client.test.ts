// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiDownload, apiGet, apiPost, buildQuery, toApiError } from "@/lib/api/client";

/** Envelope codes and statuses of doc 05 section 2. */
const ENVELOPE_CASES: [number, string][] = [
  [400, "bad_request"],
  [404, "not_found"],
  [422, "validation_error"],
  [500, "internal_error"],
  [502, "llm_unavailable"],
];

function envelope(code: string) {
  return {
    error: {
      code,
      message: "Investigation 'XYZ' not found",
      details: code === "validation_error" ? [{ loc: ["body", "lens"], msg: "required" }] : null,
      request_id: "req-42",
    },
  };
}

function stubFetch(response: Response) {
  const fetchMock = vi.fn(async () => response);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function requestOf(fetchMock: ReturnType<typeof stubFetch>): [string, RequestInit | undefined] {
  return fetchMock.mock.calls[0] as unknown as [string, RequestInit | undefined];
}

afterEach(() => vi.unstubAllGlobals());

describe("error envelope to ApiError (doc 05 section 2, doc 10 section 7)", () => {
  it.each(ENVELOPE_CASES)(
    "FR-15: HTTP %i maps code %s and every envelope field",
    async (status, code) => {
      stubFetch(Response.json(envelope(code), { status }));
      const failure = apiGet("/investigations/XYZ");
      await expect(failure).rejects.toBeInstanceOf(ApiError);
      await expect(failure).rejects.toMatchObject({
        status,
        code,
        message: "Investigation 'XYZ' not found",
        details: envelope(code).error.details,
        requestId: "req-42",
        name: "ApiError",
      });
    },
  );

  it("FR-15: a body that is not the envelope becomes internal_error with the X-Request-ID header", async () => {
    const response = new Response("upstream timeout", {
      status: 504,
      headers: { "X-Request-ID": "req-7" },
    });
    const error = await toApiError(response);
    expect(error).toMatchObject({
      status: 504,
      code: "internal_error",
      requestId: "req-7",
      details: null,
    });
  });

  it("FR-15: POST failures are mapped the same way", async () => {
    stubFetch(Response.json(envelope("bad_request"), { status: 400 }));
    await expect(apiPost("/compare", { investigations: ["BASS-II"] })).rejects.toMatchObject({
      status: 400,
      code: "bad_request",
    });
  });
});

describe("requests under /api/v1 (doc 05 sections 1 and 4)", () => {
  it("FR-02: apiGet uses the base path and repeats list parameters", async () => {
    const fetchMock = stubFetch(Response.json({ items: [] }));
    await apiGet("/investigations", {
      fuel_phase: ["solid", "gas"],
      q: "flame",
      page: 2,
      tag: [],
      o2_min: null,
    });
    const [url] = requestOf(fetchMock);
    expect(url).toBe("/api/v1/investigations?fuel_phase=solid&fuel_phase=gas&q=flame&page=2");
  });

  it("FR-02: buildQuery drops empty values", () => {
    expect(buildQuery(undefined)).toBe("");
    expect(buildQuery({ q: "", sector: undefined, page: null })).toBe("");
  });

  it("FR-03: apiPost sends a JSON body and returns the parsed response", async () => {
    const fetchMock = stubFetch(Response.json({ lens: "habitat", items: [] }));
    const body = { lens: "habitat", limit: 24 };
    await expect(apiPost("/rank", body)).resolves.toEqual({ lens: "habitat", items: [] });
    const [url, init] = requestOf(fetchMock);
    expect(url).toBe("/api/v1/rank");
    expect(init?.method).toBe("POST");
    expect(new Headers(init?.headers).get("Content-Type")).toBe("application/json");
    expect(JSON.parse(String(init?.body))).toEqual(body);
  });

  it("FR-08: apiDownload takes the file name from Content-Disposition", async () => {
    const headers = {
      "Content-Type": "text/csv",
      "Content-Disposition": 'attachment; filename="flamescope-runs.csv"',
    };
    stubFetch(new Response("# rubric_version: 2026.11-1\ninvestigation\n", { headers }));
    const file = await apiDownload("/extract/export", { filters: {}, format: "csv" });
    expect(file.filename).toBe("flamescope-runs.csv");
    expect(await file.blob.text()).toContain("investigation");
  });
});
