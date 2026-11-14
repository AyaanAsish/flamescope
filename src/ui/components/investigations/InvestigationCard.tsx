"use client";

import { BadgeCheck, Check, Plus } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { PhaseBadge } from "@/components/ui/phase-badge";
import type { InvestigationSummary, Lens } from "@/lib/api/types";
import { LENSES, LENS_COLORS, LENS_LABELS } from "@/lib/constants";
import {
  formatFlowRange,
  formatLabel,
  formatOxygenRange,
  formatPressureRange,
  formatScore,
} from "@/lib/format";
import { cn } from "@/lib/utils";

interface InvestigationCardProps {
  investigation: InvestigationSummary;
  isSelectedForCompare: boolean;
  onToggleCompare: (acronym: string) => void;
}

function LensScores({ investigation }: { investigation: InvestigationSummary }) {
  return (
    <dl className="border-line grid grid-cols-4 gap-2 border-t pt-3">
      {[...LENSES, "overall" as const].map((lens) => (
        <div key={lens}>
          <dt className="text-muted flex items-center gap-1 text-xs">
            {lens === "overall" ? null : (
              <span
                aria-hidden
                className="size-1.5 rounded-full"
                style={{ backgroundColor: LENS_COLORS[lens as Lens] }}
              />
            )}
            {LENS_LABELS[lens]}
          </dt>
          <dd className="mono text-sm font-medium">{formatScore(investigation.scores[lens])}</dd>
        </div>
      ))}
    </dl>
  );
}

function ConditionRanges({ investigation }: { investigation: InvestigationSummary }) {
  const rows: [string, string][] = [
    ["Oxygen", formatOxygenRange(investigation.o2_range)],
    ["Pressure", formatPressureRange(investigation.pressure_range_kpa)],
    ["Flow", formatFlowRange(investigation.flow_range_cm_s)],
  ];
  return (
    <dl className="text-caption space-y-1">
      {rows.map(([label, value]) => (
        <div key={label} className="flex justify-between gap-3">
          <dt className="text-muted">{label}</dt>
          <dd className="mono text-muted text-right">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function InvestigationCard({
  investigation,
  isSelectedForCompare,
  onToggleCompare,
}: InvestigationCardProps) {
  const href = `/investigations/${encodeURIComponent(investigation.acronym)}`;
  return (
    <article
      data-testid="investigation-card"
      data-acronym={investigation.acronym}
      className="rounded-card border-line bg-surface1 hover:border-line-strong flex flex-col gap-3 border p-5 transition-colors"
    >
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <Link href={href} className="hover:text-accent text-base font-semibold">
            {investigation.acronym}
          </Link>
          <p className="text-caption text-muted line-clamp-2">{investigation.title}</p>
        </div>
        {investigation.reviewed ? (
          <Badge tone="success">
            <BadgeCheck className="size-3" aria-hidden /> Reviewed
          </Badge>
        ) : (
          <Badge>Unreviewed</Badge>
        )}
      </header>
      <div className="flex flex-wrap gap-1.5">
        {investigation.fuel_phases.map((phase) => (
          <PhaseBadge key={phase} phase={phase} />
        ))}
        {investigation.platform ? <Badge>{investigation.platform}</Badge> : null}
        {investigation.gravity_level ? (
          <Badge tone="cool">{formatLabel(investigation.gravity_level)}</Badge>
        ) : null}
      </div>
      <p className="text-muted line-clamp-3 text-sm">
        {investigation.summary ?? "No curated summary yet."}
      </p>
      <ConditionRanges investigation={investigation} />
      <LensScores investigation={investigation} />
      <button
        type="button"
        aria-pressed={isSelectedForCompare}
        onClick={() => onToggleCompare(investigation.acronym)}
        className={cn(
          "rounded-control text-caption mt-auto flex h-8 items-center justify-center gap-1.5 border font-medium transition-colors",
          isSelectedForCompare
            ? "border-accent bg-accent-soft text-accent"
            : "border-line bg-surface2 text-muted hover:border-line-strong hover:text-fg",
        )}
      >
        {isSelectedForCompare ? (
          <Check className="size-3.5" aria-hidden />
        ) : (
          <Plus className="size-3.5" aria-hidden />
        )}
        {isSelectedForCompare ? "Selected for compare" : "Add to compare"}
      </button>
    </article>
  );
}
