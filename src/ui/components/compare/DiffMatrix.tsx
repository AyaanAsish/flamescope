"use client";

import { Equal, EqualNot } from "lucide-react";
import { Table, Td, Th } from "@/components/ui/table";
import type { Json, MatrixRow, OpenRangePair } from "@/lib/api/types";
import {
  formatBytes,
  formatCell,
  formatFlowRange,
  formatOxygenRange,
  formatPressureRange,
  NOT_AVAILABLE,
} from "@/lib/format";
import { cn } from "@/lib/utils";

type ValueFormatter = (value: Json) => string;

function asRange(value: Json): OpenRangePair | null {
  return Array.isArray(value) &&
    value.length === 2 &&
    value.every((item) => item === null || typeof item === "number")
    ? (value as OpenRangePair)
    : null;
}

const FORMATTERS: Record<string, ValueFormatter> = {
  o2_range: (value) => formatOxygenRange(asRange(value)),
  pressure_range_kpa: (value) => formatPressureRange(asRange(value)),
  flow_range_cm_s: (value) => formatFlowRange(asRange(value)),
  data_volume: (value) => (typeof value === "number" ? formatBytes(value) : formatCell(value)),
};

export function formatMatrixValue(attribute: string, value: Json | undefined): string {
  if (value === undefined || value === null) return NOT_AVAILABLE;
  return (FORMATTERS[attribute] ?? formatCell)(value);
}

interface DiffMatrixProps {
  rows: MatrixRow[];
  acronyms: string[];
}

export function DiffMatrix({ rows, acronyms }: DiffMatrixProps) {
  return (
    <div data-testid="diff-matrix">
      <Table label="Comparison matrix">
        <thead>
          <tr>
            <Th className="w-56">Attribute</Th>
            {acronyms.map((acronym) => (
              <Th key={acronym}>{acronym}</Th>
            ))}
            <Th className="w-28">Match</Th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.attribute}
              data-same={row.same}
              className={cn(row.same ? "" : "bg-accent-soft")}
            >
              <Td className="font-medium">
                {row.label}
                <span className="text-muted block text-xs font-normal">{row.group}</span>
              </Td>
              {acronyms.map((acronym) => (
                <Td key={acronym} className="mono">
                  {formatMatrixValue(row.attribute, row.values[acronym])}
                </Td>
              ))}
              <Td>
                {row.same ? (
                  <span className="text-muted flex items-center gap-1.5">
                    <Equal className="size-4" aria-hidden /> Same
                  </span>
                ) : (
                  <span className="text-accent flex items-center gap-1.5 font-medium">
                    <EqualNot className="size-4" aria-hidden /> Different
                  </span>
                )}
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  );
}
