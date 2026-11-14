"use client";

import { Send, Square } from "lucide-react";
import { useState, type KeyboardEvent } from "react";
import { MessageList } from "@/components/ask/MessageList";
import { SourcesPanel } from "@/components/ask/SourcesPanel";
import { useAsk } from "@/components/ask/use-ask";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { SourceRef } from "@/lib/api/types";
import { SUGGESTED_QUESTIONS } from "@/lib/constants";

export function ChatPanel() {
  const { messages, ask, stop, isStreaming } = useAsk();
  const [text, setText] = useState("");
  const [activeSource, setActiveSource] = useState<SourceRef | null>(null);

  function submit(question: string) {
    const trimmed = question.trim();
    if (!trimmed || isStreaming) return;
    setText("");
    setActiveSource(null);
    void ask(trimmed);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== "Enter" || event.shiftKey) return;
    event.preventDefault();
    submit(text);
  }

  return (
    <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="space-y-6">
        {messages.length === 0 ? (
          <Card>
            <p className="text-muted mb-3 text-sm">
              Answers use only the curated PSI corpus and cite their sources. Try one of these:
            </p>
            <ul className="flex flex-wrap gap-2">
              {SUGGESTED_QUESTIONS.map((question) => (
                <li key={question}>
                  <Button size="sm" onClick={() => submit(question)}>
                    {question}
                  </Button>
                </li>
              ))}
            </ul>
          </Card>
        ) : (
          <MessageList
            messages={messages}
            activeSource={activeSource}
            onSelectCitation={setActiveSource}
          />
        )}
        <form
          onSubmit={(event) => {
            event.preventDefault();
            submit(text);
          }}
          className="bg-bg sticky bottom-0 flex items-end gap-2 pt-2 pb-4"
        >
          <label htmlFor="ask-input" className="sr-only">
            Question
          </label>
          <textarea
            id="ask-input"
            data-testid="ask-input"
            value={text}
            disabled={isStreaming}
            rows={2}
            placeholder="Ask about the investigations, for example which tested solids above 30 % oxygen"
            onChange={(event) => setText(event.target.value)}
            onKeyDown={onKeyDown}
            className="rounded-card border-line bg-surface1 text-fg placeholder:text-muted hover:border-line-strong min-h-14 flex-1 resize-none border px-4 py-3 text-sm disabled:opacity-60"
          />
          {isStreaming ? (
            <Button type="button" onClick={stop}>
              <Square className="size-4" aria-hidden /> Stop
            </Button>
          ) : (
            <Button type="submit" variant="primary" disabled={!text.trim()}>
              <Send className="size-4" aria-hidden /> Ask
            </Button>
          )}
        </form>
      </div>
      <SourcesPanel message={messages.at(-1)} activeSource={activeSource} />
    </div>
  );
}
