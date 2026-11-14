"use client";

import { Sparkles } from "lucide-react";
import { SourceLink } from "@/components/investigations/SourceLink";
import { Card, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { Narrative } from "@/lib/api/types";

interface NarrativePanelProps {
  narrative: Narrative | undefined;
  isLoading: boolean;
  title?: string;
  testId?: string;
}

function NarrativeBody({ narrative }: { narrative: Narrative }) {
  if (narrative.status === "unavailable") {
    return (
      <p className="text-muted text-sm">
        The language model is unavailable, so no written summary was generated. The matrix above is
        unaffected.
      </p>
    );
  }
  if (narrative.status === "skipped" || narrative.sentences.length === 0) {
    return (
      <p className="text-muted text-sm">No written summary was generated for this selection.</p>
    );
  }
  return (
    <ol className="space-y-3">
      {narrative.sentences.map((sentence, index) => (
        <li key={index} className="space-y-1">
          <p className="text-sm">{sentence.text}</p>
          <div className="flex flex-wrap gap-x-3">
            {sentence.citations.map((source, citationIndex) => (
              <SourceLink key={`${source.uri}-${citationIndex}`} source={source} />
            ))}
          </div>
        </li>
      ))}
    </ol>
  );
}

export function NarrativePanel({
  narrative,
  isLoading,
  title = "Narrative",
  testId,
}: NarrativePanelProps) {
  return (
    <Card data-testid={testId}>
      <CardHeader
        title={title}
        description="Generated from the matrix facts; each sentence is checked against its cited source."
      />
      {isLoading || !narrative ? (
        <div className="space-y-2" role="status" aria-label="Generating narrative">
          <Skeleton className="h-4" />
          <Skeleton className="h-4 w-5/6" />
          <Skeleton className="h-4 w-2/3" />
        </div>
      ) : (
        <>
          <p className="text-muted mb-3 flex items-center gap-1.5 text-xs">
            <Sparkles className="size-3.5" aria-hidden /> AI-assisted text
          </p>
          <NarrativeBody narrative={narrative} />
        </>
      )}
    </Card>
  );
}
