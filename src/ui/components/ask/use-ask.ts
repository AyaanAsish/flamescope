"use client";

import { useCallback, useRef, useState } from "react";
import { streamAsk } from "@/lib/api/sse";
import type { AskError, AskMeta, VerifiedSentence } from "@/lib/api/types";

export interface AskMessage {
  id: number;
  question: string;
  draft: string;
  sentences: VerifiedSentence[] | null;
  dropped: number;
  meta: AskMeta | null;
  related: string[];
  status: "streaming" | "done" | "error";
  error: AskError | null;
}

type MessagePatch = Partial<AskMessage>;

function newMessage(id: number, question: string): AskMessage {
  return {
    id,
    question,
    draft: "",
    sentences: null,
    dropped: 0,
    meta: null,
    related: [],
    status: "streaming",
    error: null,
  };
}

export function useAsk() {
  const [messages, setMessages] = useState<AskMessage[]>([]);
  const abortRef = useRef<AbortController | null>(null);
  const nextId = useRef(1);

  const update = useCallback((id: number, patch: (message: AskMessage) => MessagePatch) => {
    setMessages((current) =>
      current.map((message) => (message.id === id ? { ...message, ...patch(message) } : message)),
    );
  }, []);

  const ask = useCallback(
    async (question: string) => {
      const id = nextId.current++;
      const controller = new AbortController();
      abortRef.current = controller;
      setMessages((current) => [...current, newMessage(id, question)]);
      try {
        await streamAsk(
          { question, filters: { investigations: [] } },
          {
            onMeta: (meta) => update(id, () => ({ meta })),
            onToken: (text) => update(id, (message) => ({ draft: message.draft + text })),
            onCitations: (citations) =>
              update(id, () => ({ sentences: citations.sentences, dropped: citations.dropped })),
            onRelated: (related) => update(id, () => ({ related })),
            onDone: () => update(id, () => ({ status: "done" })),
            onError: (error) => update(id, () => ({ status: "error", error })),
          },
          controller.signal,
        );
        update(id, (message) => (message.status === "streaming" ? { status: "done" } : {}));
      } catch (error) {
        if (controller.signal.aborted) return update(id, () => ({ status: "done" }));
        const message = error instanceof Error ? error.message : "The request failed.";
        update(id, () => ({ status: "error", error: { code: "internal_error", message } }));
      }
    },
    [update],
  );

  const stop = useCallback(() => abortRef.current?.abort(), []);
  const isStreaming = messages.some((message) => message.status === "streaming");
  return { messages, ask, stop, isStreaming };
}
