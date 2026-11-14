"use client";

import { Card, CardHeader } from "@/components/ui/card";
import { DataPanel } from "@/components/ui/panel-state";
import { useVariables } from "@/lib/api/hooks";
import type { Json } from "@/lib/api/types";
import { formatCell, formatLabel, fractionToPercent } from "@/lib/format";

function withUnit(value: Json, unit: string | null): string {
  if (unit === "fraction" && typeof value === "number")
    return `${formatCell(fractionToPercent(value))} % O\u2082`;
  return unit ? `${formatCell(value)} ${unit}` : formatCell(value);
}

export function VariablesPanel({ id }: { id: string }) {
  const variables = useVariables(id);
  return (
    <DataPanel
      query={variables}
      isEmpty={(data) => data.varied.length === 0 && data.fixed.length === 0}
      emptyMessage="No varied or fixed parameters are recorded."
    >
      {(data) => (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader
              title="Varied parameters"
              description={`Change between the ${data.run_count} runs.`}
            />
            <ul className="space-y-3">
              {data.varied.map((parameter) => (
                <li key={parameter.name}>
                  <p className="text-sm font-medium">{formatLabel(parameter.name)}</p>
                  <p className="mono text-caption text-muted">
                    {parameter.values.map((value) => withUnit(value, parameter.unit)).join(", ")}
                  </p>
                </li>
              ))}
            </ul>
          </Card>
          <Card>
            <CardHeader title="Fixed parameters" description="Held constant across the runs." />
            <dl className="space-y-3">
              {data.fixed.map((parameter) => (
                <div key={parameter.name} className="flex justify-between gap-4">
                  <dt className="text-muted text-sm">{formatLabel(parameter.name)}</dt>
                  <dd className="mono text-sm">{withUnit(parameter.value, parameter.unit)}</dd>
                </div>
              ))}
            </dl>
          </Card>
        </div>
      )}
    </DataPanel>
  );
}
