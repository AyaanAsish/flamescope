"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { axisTick, chartTooltipStyle } from "@/components/charts/chart-style";

export interface TimelinePoint {
  year: number;
  count: number;
}

export function Timeline({ points, label }: { points: TimelinePoint[]; label: string }) {
  return (
    <div className="h-48 w-full">
      <ResponsiveContainer>
        <BarChart data={points} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey="year" tick={axisTick} stroke="var(--border)" />
          <YAxis allowDecimals={false} tick={axisTick} stroke="var(--border)" width={32} />
          <Tooltip {...chartTooltipStyle} formatter={(value) => [value, label]} />
          <Bar dataKey="count" fill="var(--cool)" radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
