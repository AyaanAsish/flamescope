import type { BreakdownItem, Lens } from "@/lib/api/types";
import { LENS_COLORS } from "@/lib/constants";
import { formatScore } from "@/lib/format";

const SEGMENT_OPACITY = [1, 0.8, 0.62, 0.46, 0.32];
const MAX_SCORE = 100;

export interface ScoreSegment {
  key: string;
  label: string;
  contribution: number;
  color: string;
  opacity: number;
}

export function segmentsFromBreakdown(breakdown: BreakdownItem[], lens: Lens): ScoreSegment[] {
  return breakdown
    .filter((item) => item.value !== null && item.contribution > 0)
    .map((item, index) => ({
      key: item.criterion,
      label: item.label,
      contribution: item.contribution,
      color: LENS_COLORS[lens],
      opacity: SEGMENT_OPACITY[index % SEGMENT_OPACITY.length] ?? 1,
    }));
}

export function segmentsFromLenses(
  lensScores: Partial<Record<Lens, number | null>>,
  lensWeights: Record<Lens, number>,
): ScoreSegment[] {
  const scored = (Object.keys(lensWeights) as Lens[]).filter(
    (lens) => typeof lensScores[lens] === "number",
  );
  const totalWeight = scored.reduce((sum, lens) => sum + lensWeights[lens], 0);
  if (totalWeight === 0) return [];
  return scored.map((lens) => ({
    key: lens,
    label: `${lens} lens`,
    contribution: (lensWeights[lens] * (lensScores[lens] ?? 0)) / totalWeight,
    color: LENS_COLORS[lens],
    opacity: 1,
  }));
}

interface StackedScoreBarProps {
  segments: ScoreSegment[];
  score: number | null;
  label: string;
}

/** Horizontal bar whose segments add up to the 0-100 score. */
export function StackedScoreBar({ segments, score, label }: StackedScoreBarProps) {
  return (
    <div className="flex items-center gap-3">
      <div
        role="img"
        aria-label={`${label} score ${formatScore(score)} out of 100`}
        className="bg-surface2 flex h-2.5 w-full min-w-24 overflow-hidden rounded-full"
      >
        {segments.map((segment) => (
          <span
            key={segment.key}
            title={`${segment.label}: ${formatScore(segment.contribution)} points`}
            className="border-surface1 h-full border-r last:border-r-0"
            style={{
              width: `${(segment.contribution / MAX_SCORE) * 100}%`,
              backgroundColor: segment.color,
              opacity: segment.opacity,
            }}
          />
        ))}
      </div>
      <span className="mono w-12 shrink-0 text-right text-sm font-medium">
        {formatScore(score)}
      </span>
    </div>
  );
}
