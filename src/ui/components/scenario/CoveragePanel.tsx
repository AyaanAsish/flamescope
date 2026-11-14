"use client";

import { CoverageBars, type CoverageBarRow } from "@/components/charts/CoverageBars";
import { Card, CardHeader } from "@/components/ui/card";
import type { CoverageEntry, ResolvedScenario } from "@/lib/api/types";
import {
  formatFlow,
  formatGravity,
  formatOxygen,
  formatPressure,
  type PressureUnit,
} from "@/lib/format";

interface CoveragePanelProps {
  coverage: Record<string, CoverageEntry>;
  scenario: ResolvedScenario;
  unit: PressureUnit;
}

function buildRows({ coverage, scenario, unit }: CoveragePanelProps): CoverageBarRow[] {
  const specs: Omit<CoverageBarRow, "entry">[] = [
    {
      key: "o2_fraction",
      label: "Oxygen",
      scenarioValue: scenario.o2_fraction,
      format: formatOxygen,
    },
    {
      key: "pressure_kpa",
      label: "Pressure",
      scenarioValue: scenario.pressure_kpa,
      format: (value) => formatPressure(value, unit),
    },
    {
      key: "flow_speed_cm_s",
      label: "Flow speed",
      scenarioValue: scenario.flow_speed_cm_s,
      format: formatFlow,
    },
    {
      key: "gravity_g",
      label: "Gravity",
      scenarioValue: scenario.gravity_g,
      format: formatGravity,
    },
  ];
  return specs.flatMap((spec) => {
    const entry = coverage[spec.key];
    return entry ? [{ ...spec, entry }] : [];
  });
}

export function CoveragePanel(props: CoveragePanelProps) {
  return (
    <Card data-testid="coverage-panel">
      <CardHeader
        title="Catalog coverage"
        description="Whether the scenario lies inside the conditions the catalog has tested."
      />
      <CoverageBars rows={buildRows(props)} />
    </Card>
  );
}
