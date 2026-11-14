"use client";

import type { SourceRef } from "@/lib/api/types";
import { cn } from "@/lib/utils";

interface CitationChipProps {
  index: number;
  source: SourceRef;
  isActive: boolean;
  onSelect: (source: SourceRef) => void;
}

export function CitationChip({ index, source, isActive, onSelect }: CitationChipProps) {
  return (
    <button
      type="button"
      data-testid="citation-chip"
      title={source.quote ?? source.title ?? source.uri}
      aria-pressed={isActive}
      onClick={() => onSelect(source)}
      className={cn(
        "mono rounded-control mx-0.5 inline-flex h-5 min-w-5 items-center justify-center border px-1 align-baseline text-xs transition-colors",
        isActive
          ? "border-accent bg-accent-soft text-accent"
          : "border-line-strong bg-surface2 text-cool hover:border-cool",
      )}
    >
      {index}
    </button>
  );
}
