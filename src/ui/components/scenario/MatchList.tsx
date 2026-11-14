"use client";

import Link from "next/link";
import { Card } from "@/components/ui/card";
import type { ScenarioMatch } from "@/lib/api/types";
import {
  formatFlow,
  formatGravity,
  formatOxygen,
  formatPressure,
  formatScore,
  formatSpreadRate,
  fractionToPercent,
} from "@/lib/format";

const MATCHING_RUN_THRESHOLD_PERCENT = 60;
const DIMENSION_LABELS: Record<string, string> = {
  o2: "Oxygen",
  pressure: "Pressure",
  flow: "Flow",
  fuel: "Fuel",
};

function DimensionBars({ perDimension }: { perDimension: Record<string, number> }) {
  return (
    <dl className="grid grid-cols-4 gap-3">
      {Object.entries(DIMENSION_LABELS).map(([key, label]) => {
        const similarity = perDimension[key];
        return (
          <div key={key}>
            <dt className="text-muted flex justify-between text-xs">
              {label}
              <span className="mono text-muted">
                {similarity === undefined
                  ? "n/a"
                  : `${formatScore(fractionToPercent(similarity))} %`}
              </span>
            </dt>
            <dd className="bg-surface2 mt-1 h-1.5 rounded-full">
              <div
                className="bg-cool h-full rounded-full"
                style={{ width: `${fractionToPercent(similarity ?? 0)}%` }}
              />
            </dd>
          </div>
        );
      })}
    </dl>
  );
}

function BestRun({ match }: { match: ScenarioMatch }) {
  const run = match.best_run;
  if (!run) return null;
  const { condition } = run;
  return (
    <p className="mono text-muted text-xs">
      Best run {run.label}: {formatOxygen(condition.o2_fraction)},{" "}
      {formatPressure(condition.pressure_kpa)}, {formatFlow(condition.flow_speed_cm_s)},{" "}
      {formatGravity(condition.gravity_g)}, spread{" "}
      {formatSpreadRate(run.outcome.flame_spread_rate_mm_s)}
    </p>
  );
}

export function MatchList({ matches }: { matches: ScenarioMatch[] }) {
  return (
    <ol className="space-y-3">
      {matches.map((match, index) => (
        <li key={match.acronym}>
          <Card data-testid="scenario-match" data-acronym={match.acronym} className="space-y-3">
            <div className="flex items-start justify-between gap-4">
              <div>
                <span className="mono text-muted mr-2 text-xs">#{index + 1}</span>
                <Link
                  href={`/investigations/${encodeURIComponent(match.acronym)}`}
                  className="hover:text-accent text-base font-semibold"
                >
                  {match.acronym}
                </Link>
                <p className="text-caption text-muted">
                  {match.matching_runs} runs at {MATCHING_RUN_THRESHOLD_PERCENT} % similarity or
                  better. Median run similarity{" "}
                  {formatScore(fractionToPercent(match.median_similarity))} %.
                </p>
              </div>
              <div className="text-right">
                <p className="mono text-2xl font-semibold">
                  {formatScore(fractionToPercent(match.similarity))} %
                </p>
                <p className="text-muted text-xs">best-run similarity</p>
              </div>
            </div>
            <DimensionBars perDimension={match.per_dimension} />
            <BestRun match={match} />
          </Card>
        </li>
      ))}
    </ol>
  );
}
