"use client";

import { Badge } from "@/components/ui/badge";
import { Sheet } from "@/components/ui/sheet";
import { SourceLink } from "@/components/investigations/SourceLink";
import type { BreakdownItem } from "@/lib/api/types";
import { formatScore } from "@/lib/format";

const MAX_RATING = 5;
const PERCENT = 100;

function RatingPips({ value }: { value: number | null }) {
  return (
    <span
      className="flex items-center gap-1"
      aria-label={value === null ? "No evidence" : `${value} of ${MAX_RATING}`}
    >
      {Array.from({ length: MAX_RATING }, (_, index) => (
        <span
          key={index}
          aria-hidden
          className={`size-2 rounded-full ${value !== null && index < value ? "bg-accent" : "bg-surface2 ring-line-strong ring-1"}`}
        />
      ))}
      <span className="mono text-muted ml-1 text-xs">
        {value === null ? "no evidence" : `${value} / ${MAX_RATING}`}
      </span>
    </span>
  );
}

export function BreakdownList({ breakdown }: { breakdown: BreakdownItem[] }) {
  return (
    <ul className="space-y-4">
      {breakdown.map((item) => (
        <li key={item.criterion} className="rounded-control border-line bg-surface2/40 border p-3">
          <div className="flex items-center justify-between gap-3">
            <p className="font-medium">{item.label}</p>
            <Badge>{item.origin}</Badge>
          </div>
          <div className="mt-1 flex items-center justify-between gap-3">
            <RatingPips value={item.value} />
            <span className="mono text-muted text-xs">
              weight {formatScore(item.weight * PERCENT)} %, contributes{" "}
              {formatScore(item.contribution)} points
            </span>
          </div>
          {item.rationale ? <p className="text-caption text-muted mt-2">{item.rationale}</p> : null}
          {item.evidence.length ? (
            <ul className="mt-2 space-y-1">
              {item.evidence.map((source, index) => (
                <li key={`${source.uri}-${index}`}>
                  <SourceLink source={source} />
                </li>
              ))}
            </ul>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

export interface EvidenceSection {
  title: string;
  breakdown: BreakdownItem[];
}

interface EvidenceDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  sections: EvidenceSection[];
}

export function EvidenceDrawer({
  open,
  onOpenChange,
  title,
  description,
  sections,
}: EvidenceDrawerProps) {
  return (
    <Sheet
      open={open}
      onOpenChange={onOpenChange}
      title={title}
      description={description}
      testId="evidence-drawer"
    >
      <div className="space-y-6">
        {sections.length === 0 ? (
          <p className="text-muted text-sm">No evidence is recorded for this score.</p>
        ) : null}
        {sections.map((section) => (
          <section key={section.title}>
            <h3 className="mb-3 text-sm font-semibold">{section.title}</h3>
            <BreakdownList breakdown={section.breakdown} />
          </section>
        ))}
      </div>
    </Sheet>
  );
}
