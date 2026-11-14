"use client";

import { SourceLink } from "@/components/investigations/SourceLink";
import { Card, CardHeader } from "@/components/ui/card";
import type { AskMessage } from "@/components/ask/use-ask";
import type { SourceRef } from "@/lib/api/types";
import { formatScore } from "@/lib/format";
import { cn } from "@/lib/utils";

interface SourcesPanelProps {
  message: AskMessage | undefined;
  activeSource: SourceRef | null;
}

export function SourcesPanel({ message, activeSource }: SourcesPanelProps) {
  const retrieved = message?.meta?.retrieved ?? [];
  return (
    <Card data-testid="ask-sources" className="sticky top-0 space-y-4 self-start">
      <CardHeader
        title="Sources"
        description="Chunks retrieved for the latest question, ranked by fused relevance."
      />
      {retrieved.length === 0 ? (
        <p className="text-muted text-sm">
          {message ? "No sources were retrieved." : "Sources appear here after you ask a question."}
        </p>
      ) : (
        <ul className="space-y-2">
          {retrieved.map((chunk) => (
            <li
              key={chunk.chunk_id}
              aria-current={activeSource?.chunk_id === chunk.chunk_id ? "true" : undefined}
              className={cn(
                "rounded-control border p-3 transition-colors",
                activeSource?.chunk_id === chunk.chunk_id
                  ? "border-accent bg-accent-soft"
                  : "border-line bg-surface2/40",
              )}
            >
              <p className="text-sm font-medium">{chunk.acronym}</p>
              <p className="text-caption text-muted">{chunk.doc_title}</p>
              <p className="mono text-muted text-xs">relevance {formatScore(chunk.score)}</p>
            </li>
          ))}
        </ul>
      )}
      {activeSource ? (
        <div className="border-line space-y-1 border-t pt-3">
          <p className="text-muted text-xs font-medium tracking-wide uppercase">
            Selected citation
          </p>
          {activeSource.quote ? (
            <blockquote className="border-accent text-caption text-muted border-l-2 pl-3">
              {activeSource.quote}
            </blockquote>
          ) : null}
          <SourceLink source={activeSource} />
        </div>
      ) : null}
    </Card>
  );
}
