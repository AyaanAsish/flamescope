"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { FieldLabel, Input, Select } from "@/components/ui/input";
import { NumberField } from "@/components/ui/number-field";
import { Slider } from "@/components/ui/slider";
import { resolveDisplayValues, type ScenarioValues } from "@/components/scenario/scenario-values";
import type { PresetsResponse, ScenarioPreset } from "@/lib/api/types";
import { FUEL_PHASES, PHASE_LABELS } from "@/lib/constants";
import { formatLabel, kpaToPsi, psiToKpa, roundTo, type PressureUnit } from "@/lib/format";

type ParamKey = "preset" | "o2" | "p" | "g" | "flow" | "phase" | "material" | "unit";
type ChangeHandler = (patch: Partial<Record<ParamKey, string | number | null>>) => void;

const PRESSURE_RANGE: Record<PressureUnit, { max: number; step: number; sliderStep: number }> = {
  kPa: { max: 110, step: 1, sliderStep: 0.5 },
  psi: { max: 16, step: 0.1, sliderStep: 0.1 },
};
const DISPLAY_DIGITS = 3;
// psi is shown to 0.1 psi, the precision doc 08 section 4.1 states (56.5 kPa is 8.2 psi).
const PSI_DIGITS = 1;

interface ParameterFieldProps {
  label: string;
  unit: string;
  value: number | undefined;
  range: { min: number; max: number; step: number; sliderStep?: number };
  onChange: (value: number | undefined) => void;
}

function ParameterField({ label, unit, value, range, onChange }: ParameterFieldProps) {
  return (
    <div className="space-y-2">
      <NumberField
        label={label}
        unit={unit}
        value={value === undefined ? undefined : roundTo(value, DISPLAY_DIGITS)}
        step={range.step}
        min={range.min}
        max={range.max}
        onCommit={onChange}
      />
      <Slider
        label={`${label} slider`}
        value={value ?? range.min}
        min={range.min}
        max={range.max}
        step={range.sliderStep ?? range.step}
        onChange={onChange}
      />
    </div>
  );
}

function PresetField({
  values,
  presets,
  onChange,
}: Pick<ScenarioFormProps, "values" | "presets" | "onChange">) {
  const preset: ScenarioPreset | undefined = presets?.scenario[values.preset];
  return (
    <div>
      <FieldLabel htmlFor="scenario-preset">Preset</FieldLabel>
      <Select
        id="scenario-preset"
        data-testid="scenario-preset"
        value={values.preset}
        onChange={(event) =>
          onChange({ preset: event.target.value, o2: null, p: null, g: null, flow: null })
        }
      >
        <option value="">Custom</option>
        {Object.entries(presets?.scenario ?? {}).map(([name, item]) => (
          <option key={name} value={name}>
            {formatLabel(name)}
            {item.assumed_default ? " (assumed default)" : ""}
          </option>
        ))}
      </Select>
      {preset ? (
        <p className="text-caption text-muted mt-2">
          {preset.assumed_default ? (
            <Badge tone="warning" className="mr-2">
              assumed default
            </Badge>
          ) : null}
          {preset.note}
        </p>
      ) : null}
    </div>
  );
}

function PressureField({
  valueKpa,
  unit,
  onChange,
}: {
  valueKpa: number | undefined;
  unit: PressureUnit;
  onChange: ChangeHandler;
}) {
  const range = PRESSURE_RANGE[unit];
  const display =
    valueKpa === undefined
      ? undefined
      : unit === "psi"
        ? roundTo(kpaToPsi(valueKpa), PSI_DIGITS)
        : valueKpa;
  const commit = (value: number | undefined) => {
    const kpa = value === undefined ? null : roundTo(unit === "psi" ? psiToKpa(value) : value, 1);
    onChange({ p: kpa });
  };
  return (
    <div className="flex items-end justify-between gap-3">
      <div className="flex-1">
        <ParameterField
          label="Pressure"
          unit={unit}
          value={display}
          range={{ min: 0, ...range }}
          onChange={commit}
        />
      </div>
      <div
        role="group"
        aria-label="Pressure unit"
        className="border-line rounded-control flex border p-0.5"
      >
        {(["kPa", "psi"] as const).map((option) => (
          <Button
            key={option}
            size="sm"
            variant={unit === option ? "secondary" : "ghost"}
            aria-pressed={unit === option}
            onClick={() => onChange({ unit: option === "kPa" ? null : option })}
          >
            {option}
          </Button>
        ))}
      </div>
    </div>
  );
}

function FuelFields({ values, onChange }: Pick<ScenarioFormProps, "values" | "onChange">) {
  return (
    <div className="grid grid-cols-2 gap-3">
      <div>
        <FieldLabel htmlFor="scenario-phase">Fuel phase</FieldLabel>
        <Select
          id="scenario-phase"
          data-testid="scenario-phase"
          value={values.phase}
          onChange={(event) => onChange({ phase: event.target.value || null })}
        >
          <option value="">Any</option>
          {FUEL_PHASES.map((phase) => (
            <option key={phase} value={phase}>
              {PHASE_LABELS[phase]}
            </option>
          ))}
        </Select>
      </div>
      <div>
        <FieldLabel htmlFor="scenario-material">Material</FieldLabel>
        <Input
          id="scenario-material"
          data-testid="scenario-material"
          defaultValue={values.material}
          placeholder="for example PMMA"
          onBlur={(event) => onChange({ material: event.target.value || null })}
        />
      </div>
    </div>
  );
}

export interface ScenarioFormProps {
  values: ScenarioValues;
  presets: PresetsResponse | undefined;
  unit: PressureUnit;
  onChange: ChangeHandler;
  onReset: () => void;
}

export function ScenarioForm({ values, presets, unit, onChange, onReset }: ScenarioFormProps) {
  const shown = resolveDisplayValues(values, presets);
  const set = (key: ParamKey) => (value: number | undefined) => onChange({ [key]: value ?? null });
  return (
    <Card data-testid="scenario-form" className="space-y-5">
      <CardHeader
        title="Scenario"
        description="Pick a preset, then adjust any value. Gravity is used for coverage and bounding only."
      />
      <PresetField values={values} presets={presets} onChange={onChange} />
      <ParameterField
        label="Oxygen"
        unit="%"
        value={shown.o2Percent}
        range={{ min: 0, max: 100, step: 1 }}
        onChange={set("o2")}
      />
      <PressureField valueKpa={shown.pressureKpa} unit={unit} onChange={onChange} />
      <ParameterField
        label="Flow speed"
        unit="cm/s"
        value={shown.flowCmS}
        range={{ min: 0, max: 100, step: 1 }}
        onChange={set("flow")}
      />
      <ParameterField
        label="Gravity"
        unit="g"
        value={shown.gravityG}
        range={{ min: 0, max: 1, step: 0.001 }}
        onChange={set("g")}
      />
      <FuelFields values={values} onChange={onChange} />
      <Button size="sm" variant="ghost" onClick={onReset}>
        Reset scenario
      </Button>
    </Card>
  );
}
