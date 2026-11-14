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

export function ScoreRadar({ points }: { points: RadarPoint[] }) {
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer>
        <RadarChart data={points} outerRadius="75%">
          <PolarGrid stroke="var(--border)" />
          <PolarAngleAxis dataKey="axis" tick={{ fill: "var(--text-muted)", fontSize: 12 }} />
          <PolarRadiusAxis
            domain={[0, MAX_SCORE]}
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
