"use client";

import { Card, CardHeader } from "@/components/ui/card";
import { Checkbox, FieldLabel } from "@/components/ui/input";
import { NumberField } from "@/components/ui/number-field";
import { OUTCOME_KEYS } from "@/components/extract/extract-state";
import { useInvestigations } from "@/lib/api/hooks";
import { FUEL_PHASES, PHASE_LABELS } from "@/lib/constants";
import { formatLabel } from "@/lib/format";
import { parseList, parseNumber, useUrlState } from "@/lib/use-url-state";

const PICKER_PAGE_SIZE = 100;

function useToggleParam(key: string) {
  const { params, patch } = useUrlState();
  const selected = parseList(params.get(key));
  const toggle = (value: string) =>
    patch({
      [key]: (selected.includes(value)
        ? selected.filter((item) => item !== value)
        : [...selected, value]
      ).join(","),
    });
  return { selected, toggle };
}

function CheckboxGroup({
  legend,
  paramKey,
  options,
}: {
  legend: string;
  paramKey: string;
  options: { value: string; label: string }[];
}) {
  const { selected, toggle } = useToggleParam(paramKey);
  return (
    <fieldset>
      <legend className="text-muted mb-1 text-xs font-medium tracking-wide uppercase">
        {legend}
      </legend>
      <div className="max-h-48 overflow-y-auto pr-1">
        {options.map((option) => (
          <Checkbox
            key={option.value}
            label={option.label}
            checked={selected.includes(option.value)}
            onChange={() => toggle(option.value)}
          />
        ))}
      </div>
    </fieldset>
  );
}

function RangeInputs() {
  const { params, patch } = useUrlState();
  const field = (key: string, label: string, unit: string) => (
    <NumberField
      label={label}
      unit={unit}
      min={0}
      value={parseNumber(params.get(key))}
      onCommit={(value) => patch({ [key]: value })}
    />
  );
  return (
    <div className="grid grid-cols-2 gap-3">
      {field("o2_min", "O2 min", "%")}
      {field("o2_max", "O2 max", "%")}
      {field("pmin", "Pressure min", "kPa")}
      {field("pmax", "Pressure max", "kPa")}
    </div>
  );
}

export function QueryBuilder() {
  const catalog = useInvestigations({ sort: "acronym", page_size: PICKER_PAGE_SIZE });
  const investigations = (catalog.data?.items ?? []).map((item) => ({
    value: item.acronym,
    label: item.acronym,
  }));
  return (
    <Card data-testid="extract-query" className="space-y-5">
      <CardHeader title="Query" description="Filter test runs, then choose columns and export." />
      <CheckboxGroup
        legend="Fuel phase"
        paramKey="phase"
        options={FUEL_PHASES.map((phase) => ({ value: phase, label: PHASE_LABELS[phase] }))}
      />
      <div>
        <FieldLabel>Atmosphere</FieldLabel>
        <RangeInputs />
      </div>
      <CheckboxGroup
        legend="Has recorded outcome"
        paramKey="outcome"
        options={OUTCOME_KEYS.map((key) => ({ value: key, label: formatLabel(key) }))}
      />
      <CheckboxGroup legend="Investigations" paramKey="inv" options={investigations} />
    </Card>
  );
}
