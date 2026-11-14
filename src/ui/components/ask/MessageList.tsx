"use client";

import { AlertTriangle } from "lucide-react";
import { CitationChip } from "@/components/ask/CitationChip";
import type { AskMessage } from "@/components/ask/use-ask";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import type { SourceRef } from "@/lib/api/types";
import Link from "next/link";

interface MessageListProps {
  messages: AskMessage[];
  activeSource: SourceRef | null;
  onSelectCitation: (source: SourceRef) => void;
}

function sourceKey(source: SourceRef): string {
  return `${source.uri}#${source.chunk_id ?? source.locator ?? ""}`;
}

function Answer({
  message,
  activeSource,
  onSelectCitation,
}: { message: AskMessage } & Omit<MessageListProps, "messages">) {
  if (message.sentences) {
    return (
      <p className="text-sm leading-relaxed">
        {message.sentences.map((sentence, index) => (
          <span key={index} className={sentence.supported ? "" : "text-muted"}>
            {sentence.text}
            {sentence.citations.map((source, citationIndex) => (
              <CitationChip
                key={sourceKey(source)}
                index={citationIndex + 1}
                source={source}
                isActive={activeSource !== null && sourceKey(activeSource) === sourceKey(source)}
                onSelect={onSelectCitation}
              />
            ))}
            {sentence.supported ? null : (
              <Badge tone="warning" className="mx-1">
                unverified
              </Badge>
            )}{" "}
          </span>
        ))}
      </p>
    );
  }
  if (message.draft) return <p className="text-muted text-sm leading-relaxed">{message.draft}</p>;
  return message.status === "streaming" ? (
    <div className="space-y-2" role="status" aria-label="Waiting for answer">
      <Skeleton className="h-4" />
      <Skeleton className="h-4 w-4/5" />
    </div>
  ) : null;
}

function AnswerFooter({ message }: { message: AskMessage }) {
  return (
    <>
      {message.dropped > 0 ? (
        <p className="text-muted mt-2 text-xs">
          {message.dropped} sentence(s) were removed because no source supported them.
        </p>
      ) : null}
      {message.related.length ? (
        <div className="mt-3 flex flex-wrap items-center gap-1.5">
          <span className="text-muted text-xs">Related:</span>
          {message.related.map((acronym) => (
            <Link key={acronym} href={`/investigations/${encodeURIComponent(acronym)}`}>
              <Badge tone="cool">{acronym}</Badge>
            </Link>
          ))}
        </div>
      ) : null}
      {message.status === "error" && message.error ? (
        <p role="alert" className="text-caption text-danger mt-3 flex items-start gap-2">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden />
          {message.error.message} The retrieved sources remain available on the right.
        </p>
      ) : null}
    </>
  );
}

export function MessageList({ messages, activeSource, onSelectCitation }: MessageListProps) {
  return (
    <ol className="space-y-6" aria-live="polite">
      {messages.map((message) => (
        <li key={message.id} className="space-y-3">
          <p className="rounded-card border-line bg-surface2 border px-4 py-2.5 text-sm font-medium">
            {message.question}
          </p>
          <div data-testid="ask-answer" className="rounded-card border-line bg-surface1 border p-4">
            <Answer
              message={message}
              activeSource={activeSource}
              onSelectCitation={onSelectCitation}
            />
            <AnswerFooter message={message} />
          </div>
        </li>
      ))}
    </ol>
  );
}
