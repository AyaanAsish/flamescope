import { CircleCheck, CircleX, TriangleAlert, type LucideIcon } from "lucide-react";
import type { CoverageEntry, CoverageState } from "@/lib/api/types";

export interface CoverageBarRow {
  key: string;
  label: string;
  entry: CoverageEntry;
  scenarioValue: number | null;
  format: (value: number) => string;
}

const STATE_LABEL: Record<CoverageState, string> = {
  covered: "Covered",
  extrapolated: "Extrapolated",
  no_data: "No data",
};

/** Doc 10 section 2.3 rule 2: every state pairs its colour with an icon and a label. */
const STATE_ICON: Record<CoverageState, LucideIcon> = {
  covered: CircleCheck,
  extrapolated: TriangleAlert,
  no_data: CircleX,
};

const STATE_BAR: Record<CoverageState, string> = {
  covered: "bg-success",
  extrapolated: "bg-warning",
  no_data: "bg-danger",
};

const FULL_SCALE = 100;
const SCALE_PADDING = 0.1;

function scaleOf(row: CoverageBarRow): { low: number; high: number } {
  const [rangeLow, rangeHigh] = row.entry.catalog_range ?? [0, 1];
  const values = [rangeLow, rangeHigh, row.scenarioValue ?? rangeLow];
  const low = Math.min(...values);
  const high = Math.max(...values);
  const pad = (high - low || 1) * SCALE_PADDING;
  return { low: low - pad, high: high + pad };
}

function position(value: number, scale: { low: number; high: number }): number {
  return ((value - scale.low) / (scale.high - scale.low)) * FULL_SCALE;
}

function StateChip({ state }: { state: CoverageState }) {
  const Icon = STATE_ICON[state];
  return (
    <span className="rounded-control border-line bg-surface2 text-fg flex items-center gap-1 border px-1.5 py-0.5 font-medium">
      <Icon className="size-3.5" aria-hidden />
      {STATE_LABEL[state]}
    </span>
  );
}

export function CoverageBar({ row }: { row: CoverageBarRow }) {
  const { entry, scenarioValue } = row;
  const scale = scaleOf(row);
  const range = entry.catalog_range;
  return (
    <div className="space-y-1.5" data-state={entry.state}>
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">{row.label}</span>
        <span className="text-muted flex items-center gap-2 text-xs">
          <span className="mono">
            {scenarioValue === null ? "unset" : row.format(scenarioValue)}
          </span>
          <StateChip state={entry.state} />
        </span>
      </div>
      <div className="bg-surface2 relative h-2 rounded-full">
        {range ? (
          <span
            className={`absolute h-full rounded-full opacity-70 ${STATE_BAR[entry.state]}`}
            style={{
              left: `${position(range[0], scale)}%`,
              width: `${Math.max(position(range[1], scale) - position(range[0], scale), 1)}%`,
            }}
          />
        ) : null}
        {scenarioValue === null ? null : (
          <span
            className="bg-fg absolute -top-1 h-4 w-0.5 rounded-full"
            style={{ left: `${position(scenarioValue, scale)}%` }}
            title="Scenario value"
          />
        )}
      </div>
      <p className="mono text-muted text-xs">
        {range
          ? `Catalog ${row.format(range[0])} to ${row.format(range[1])}`
          : entry.catalog_values
            ? `Catalog values: ${entry.catalog_values.map(row.format).join(", ")}`
            : "Catalog has no values"}
      </p>
    </div>
  );
}

export function CoverageBars({ rows }: { rows: CoverageBarRow[] }) {
  return (
    <div className="space-y-5">
      {rows.map((row) => (
        <CoverageBar key={row.key} row={row} />
      ))}
    </div>
  );
}
