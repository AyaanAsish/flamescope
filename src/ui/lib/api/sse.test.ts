// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "@/lib/api/client";
import { parseSseFrames, streamAsk } from "@/lib/api/sse";
import type { AskHandlers } from "@/lib/api/types";

/** The event order of doc 05 section 10. */
const DOCUMENTED_ORDER = ["meta", "token", "token", "citations", "related", "done"];

const META = {
  request_id: "req-1",
  retrieved: [{ chunk_id: 1, acronym: "BASS-II", doc_title: "Overview", score: 0.71 }],
};
const CITATIONS = {
  sentences: [
    {
      text: "Flames spread.",
      citations: [{ kind: "document", uri: "s3://nasa-psi/x.pdf" }],
      supported: true,
    },
  ],
  dropped: 1,
};

function frame(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

const DOCUMENTED_STREAM = [
  frame("meta", META),
  frame("token", { text: "Flames " }),
  frame("token", { text: "spread." }),
  frame("citations", CITATIONS),
  frame("related", { investigations: ["BASS-II", "CFI-G"] }),
  frame("done", { status: "ok" }),
].join("");

function streamResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk)));
      controller.close();
    },
  });
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

/** Splits text into pieces of `size` characters so frames straddle chunk boundaries. */
function splitEvery(text: string, size: number): string[] {
  return Array.from({ length: Math.ceil(text.length / size) }, (_, index) =>
    text.slice(index * size, (index + 1) * size),
  );
}

function recordingHandlers(log: string[]): AskHandlers {
  return {
    onMeta: () => log.push("meta"),
    onToken: () => log.push("token"),
    onCitations: () => log.push("citations"),
    onRelated: () => log.push("related"),
    onDone: () => log.push("done"),
    onError: () => log.push("error"),
  };
}

afterEach(() => vi.unstubAllGlobals());

describe("parseSseFrames (doc 10 section 7)", () => {
  it("FR-11: keeps an unfinished frame as the remainder until its blank line arrives", () => {
    const first = parseSseFrames('event: token\ndata: {"text":"Fla');
    expect(first.frames).toEqual([]);
    const second = parseSseFrames(`${first.rest}mes"}\n\n`);
    expect(second.frames).toEqual([{ event: "token", data: '{"text":"Flames"}' }]);
    expect(second.rest).toBe("");
  });

  it("FR-11: parses several events delivered in one chunk, in order", () => {
    const parsed = parseSseFrames(DOCUMENTED_STREAM);
    expect(parsed.frames.map((item) => item.event)).toEqual(DOCUMENTED_ORDER);
    expect(JSON.parse(parsed.frames[3]?.data ?? "null")).toEqual(CITATIONS);
  });

  it("FR-11: accepts CRLF line endings", () => {
    const parsed = parseSseFrames('event: done\r\ndata: {"status":"ok"}\r\n\r\n');
    expect(parsed.frames).toEqual([{ event: "done", data: '{"status":"ok"}' }]);
  });
});

describe("streamAsk (doc 05 section 10, CF-09)", () => {
  it.each([1, 7, 64])(
    "FR-11: dispatches the documented event order with %i-character chunks",
    async (size) => {
      vi.stubGlobal(
        "fetch",
        vi.fn(async () => streamResponse(splitEvery(DOCUMENTED_STREAM, size))),
      );
      const log: string[] = [];
      await streamAsk({ question: "q", filters: { investigations: [] } }, recordingHandlers(log));
      expect(log).toEqual(DOCUMENTED_ORDER);
    },
  );

  it("FR-11: passes parsed payloads to the handlers", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => streamResponse([DOCUMENTED_STREAM])),
    );
    const onMeta = vi.fn();
    const tokens: string[] = [];
    const onCitations = vi.fn();
    const onRelated = vi.fn();
    await streamAsk(
      { question: "q", filters: { investigations: [] } },
      { onMeta, onToken: (text) => tokens.push(text), onCitations, onRelated },
    );
    expect(onMeta).toHaveBeenCalledWith(META);
    expect(tokens.join("")).toBe("Flames spread.");
    expect(onCitations).toHaveBeenCalledWith(CITATIONS);
    expect(onRelated).toHaveBeenCalledWith(["BASS-II", "CFI-G"]);
  });

  it("FR-11: the terminal error event reaches onError after meta", async () => {
    const error = { code: "llm_unavailable", message: "LLM provider failed" };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => streamResponse([frame("meta", META), frame("error", error)])),
    );
    const log: string[] = [];
    const onError = vi.fn();
    await streamAsk(
      { question: "q", filters: { investigations: [] } },
      { ...recordingHandlers(log), onError },
    );
    expect(log).toEqual(["meta"]);
    expect(onError).toHaveBeenCalledWith(error);
  });

  it("FR-11: posts JSON to /api/v1/ask and asks for an event stream", async () => {
    const fetchMock = vi.fn(async () => streamResponse([frame("done", { status: "ok" })]));
    vi.stubGlobal("fetch", fetchMock);
    const body = {
      question: "Which experiments tested solids?",
      filters: { investigations: [] },
      top_k: 8,
    };
    await streamAsk(body, {});
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/v1/ask");
    expect(init.method).toBe("POST");
    expect(new Headers(init.headers).get("Accept")).toBe("text/event-stream");
    expect(JSON.parse(String(init.body))).toEqual(body);
  });

  it("FR-11: an HTTP error before the stream is raised as ApiError from the envelope", async () => {
    const envelope = {
      error: {
        code: "validation_error",
        message: "question is required",
        details: null,
        request_id: "r-9",
      },
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Response.json(envelope, { status: 422 })),
    );
    const failure = streamAsk({ question: "", filters: { investigations: [] } }, {});
    await expect(failure).rejects.toBeInstanceOf(ApiError);
    await expect(failure).rejects.toMatchObject({ status: 422, code: "validation_error" });
  });
});
