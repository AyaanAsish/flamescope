"use client";

import {
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { chartTooltipStyle } from "@/components/charts/chart-style";

export interface RadarPoint {
  axis: string;
  value: number;
}

const MAX_SCORE = 100;
// Room for the axis labels ("Controls", "Modeling") so they are never clipped by the card.
const CHART_MARGIN = { top: 16, right: 40, bottom: 16, left: 40 };
// Ticks run straight up along the Habitat spoke instead of across the Modeling edge.
const RADIUS_AXIS_ANGLE = 90;

/** The outer ring already marks 100; its label would sit on the top axis label. */
function hideOuterTick(value: number): string {
  return value >= MAX_SCORE ? "" : String(value);
}

export function ScoreRadar({ points }: { points: RadarPoint[] }) {
  return (
    <div className="h-72 w-full">
      <ResponsiveContainer>
        <RadarChart data={points} outerRadius="70%" margin={CHART_MARGIN}>
          <PolarGrid stroke="var(--border)" />
          <PolarAngleAxis dataKey="axis" tick={{ fill: "var(--text-muted)", fontSize: 12 }} />
          <PolarRadiusAxis
            angle={RADIUS_AXIS_ANGLE}
            domain={[0, MAX_SCORE]}
            tickFormatter={hideOuterTick}
            tick={{ fill: "var(--text-faint)", fontSize: 11 }}
            stroke="var(--border)"
          />
          <Radar dataKey="value" stroke="var(--accent)" fill="var(--accent)" fillOpacity={0.2} />
          <Tooltip {...chartTooltipStyle} formatter={(value) => [`${value} / 100`, "Score"]} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
