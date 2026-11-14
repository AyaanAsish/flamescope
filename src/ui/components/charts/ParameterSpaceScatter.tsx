"use client";

import { useState } from "react";
import {
  CartesianGrid,
  Legend,
  ReferenceArea,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { axisTick, chartTooltipStyle } from "@/components/charts/chart-style";
import type { FuelPhase } from "@/lib/api/types";
import { FUEL_PHASES, LUNAR_ENVELOPE, PHASE_COLORS, PHASE_LABELS } from "@/lib/constants";
import { fractionToPercent } from "@/lib/format";

export interface ScatterPoint {
  o2Percent: number;
  pressureKpa: number;
  phase: FuelPhase;
  investigation: string;
}

const PHASE_SHAPES = { gas: "circle", liquid: "diamond", solid: "square" } as const;
const PRESSURE_AXIS_MAX = 110;
const O2_AXIS: [number, number] = [0, 100];
const POINT_OPACITY = 0.75;

interface TooltipPayloadEntry {
  payload?: ScatterPoint;
}

function PointTooltip({ active, payload }: { active?: boolean; payload?: TooltipPayloadEntry[] }) {
  const point = payload?.[0]?.payload;
  if (!active || !point) return null;
  return (
    <div style={chartTooltipStyle.contentStyle} className="px-3 py-2">
      <p className="font-medium">{point.investigation}</p>
      <p className="mono text-muted text-xs">
        {PHASE_LABELS[point.phase]} fuel, {point.o2Percent.toFixed(1)} % O{"₂"},{" "}
        {point.pressureKpa.toFixed(1)} kPa
      </p>
    </div>
  );
}

const X_AXIS_LABEL = {
  value: "Oxygen (% by volume)",
  position: "insideBottom",
  offset: -12,
  fill: "var(--text-faint)",
  fontSize: 12,
} as const;

const ENVELOPE_LABEL = {
  value: "Lunar habitat envelope",
  fill: "var(--accent)",
  fontSize: 12,
  position: "insideTopRight",
} as const;

function useHiddenSeries() {
  const [hidden, setHidden] = useState<ReadonlySet<string>>(new Set());
  const toggle = (name: string) =>
    setHidden((current) => {
      const next = new Set(current);
      if (!next.delete(name)) next.add(name);
      return next;
    });
  return { hidden, toggle };
}

function LunarEnvelope() {
  return (
    <ReferenceArea
      x1={fractionToPercent(LUNAR_ENVELOPE.o2MinFraction)}
      x2={O2_AXIS[1]}
      y1={0}
      y2={LUNAR_ENVELOPE.pressureMaxKpa}
      fill="var(--accent)"
      fillOpacity={0.1}
      stroke="var(--accent)"
      strokeDasharray="4 4"
      label={ENVELOPE_LABEL}
    />
  );
}

export function ParameterSpaceScatter({ points }: { points: ScatterPoint[] }) {
  const { hidden, toggle } = useHiddenSeries();

  return (
    <div className="h-80 w-full">
      <ResponsiveContainer>
        <ScatterChart margin={{ top: 8, right: 16, bottom: 24, left: 8 }}>
          <CartesianGrid stroke="var(--border)" />
          <XAxis
            type="number"
            dataKey="o2Percent"
            domain={O2_AXIS}
            unit=" %"
            tick={axisTick}
            stroke="var(--border)"
            label={X_AXIS_LABEL}
          />
          <YAxis
            type="number"
            dataKey="pressureKpa"
            domain={[0, PRESSURE_AXIS_MAX]}
            unit=" kPa"
            tick={axisTick}
            stroke="var(--border)"
            width={64}
          />
          <LunarEnvelope />
          <Tooltip
            content={<PointTooltip />}
            cursor={{ strokeDasharray: "3 3", stroke: "var(--border-strong)" }}
          />
          <Legend
            onClick={(entry) => toggle(String(entry.value))}
            formatter={(value: string) => (
              <span
                style={{ color: hidden.has(value) ? "var(--text-faint)" : "var(--text-muted)" }}
              >
                {value}
              </span>
            )}
          />
          {FUEL_PHASES.map((phase) => (
            <Scatter
              key={phase}
              name={PHASE_LABELS[phase]}
              data={points.filter((point) => point.phase === phase)}
              fill={PHASE_COLORS[phase]}
              fillOpacity={POINT_OPACITY}
              shape={PHASE_SHAPES[phase]}
              hide={hidden.has(PHASE_LABELS[phase])}
            />
          ))}
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
