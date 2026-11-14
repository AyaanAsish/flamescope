import { API_BASE_PATH } from "@/lib/constants";
import { toApiError } from "@/lib/api/client";
import type { AskCitations, AskError, AskHandlers, AskMeta, AskRequest } from "@/lib/api/types";

export interface SseFrame {
  event: string;
  data: string;
}

const FRAME_SEPARATOR = /\r?\n\r?\n/;

function parseFrame(block: string): SseFrame | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith("event:")) event = line.slice("event:".length).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice("data:".length).trimStart());
  }
  return dataLines.length ? { event, data: dataLines.join("\n") } : null;
}

/** Splits a buffer into complete `event:` / `data:` frames and the unfinished remainder. */
export function parseSseFrames(buffer: string): { frames: SseFrame[]; rest: string } {
  const blocks = buffer.split(FRAME_SEPARATOR);
  const rest = blocks.pop() ?? "";
  const frames = blocks.map(parseFrame).filter((frame): frame is SseFrame => frame !== null);
  return { frames, rest };
}

type FrameDispatcher = (data: string) => void;

function dispatchers(handlers: AskHandlers): Record<string, FrameDispatcher> {
  return {
    meta: (data) => handlers.onMeta?.(JSON.parse(data) as AskMeta),
    token: (data) => handlers.onToken?.((JSON.parse(data) as { text: string }).text),
    citations: (data) => handlers.onCitations?.(JSON.parse(data) as AskCitations),
    related: (data) =>
      handlers.onRelated?.((JSON.parse(data) as { investigations: string[] }).investigations),
    done: () => handlers.onDone?.(),
    error: (data) => handlers.onError?.(JSON.parse(data) as AskError),
  };
}

export function dispatchFrame(frame: SseFrame, handlers: AskHandlers): void {
  dispatchers(handlers)[frame.event]?.(frame.data);
}

export async function streamAsk(
  body: AskRequest,
  handlers: AskHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_BASE_PATH}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok || !response.body) throw await toApiError(response);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parsed = parseSseFrames(buffer);
    buffer = parsed.rest;
    parsed.frames.forEach((frame) => dispatchFrame(frame, handlers));
  }
  const tail = parseSseFrames(`${buffer}\n\n`);
  tail.frames.forEach((frame) => dispatchFrame(frame, handlers));
}
