import type { FuelPhase, PresetsResponse, ScenarioRequest } from "@/lib/api/types";
import { percentToFraction } from "@/lib/format";
import { parseNumber } from "@/lib/use-url-state";

/** Scenario values as the user sees them: oxygen in percent, pressure in kPa. */
export interface ScenarioValues {
  preset: string;
  o2Percent: number | undefined;
  pressureKpa: number | undefined;
  gravityG: number | undefined;
  flowCmS: number | undefined;
  phase: FuelPhase | "";
  material: string;
}

const PERCENT = 100;

export function readScenarioValues(params: URLSearchParams): ScenarioValues {
  return {
    preset: params.get("preset") ?? "",
    o2Percent: parseNumber(params.get("o2")),
    pressureKpa: parseNumber(params.get("p")),
    gravityG: parseNumber(params.get("g")),
    flowCmS: parseNumber(params.get("flow")),
    phase: (params.get("phase") as FuelPhase | null) ?? "",
    material: params.get("material") ?? "",
  };
}

/** Explicit values override the preset; unset values fall back to it. */
export function resolveDisplayValues(
  values: ScenarioValues,
  presets: PresetsResponse | undefined,
): ScenarioValues {
  const preset = presets?.scenario[values.preset];
  if (!preset) return values;
  return {
    ...values,
    o2Percent: values.o2Percent ?? Math.round(preset.o2_fraction * PERCENT * 10) / 10,
    pressureKpa: values.pressureKpa ?? preset.pressure_kpa,
    gravityG: values.gravityG ?? preset.gravity_g,
    flowCmS: values.flowCmS ?? preset.flow_speed_cm_s,
  };
}

export function toScenarioRequest(values: ScenarioValues, explain: boolean): ScenarioRequest {
  return {
    explain,
    ...(values.preset ? { preset: values.preset } : {}),
    ...(values.o2Percent === undefined ? {} : { o2_fraction: percentToFraction(values.o2Percent) }),
    ...(values.pressureKpa === undefined ? {} : { pressure_kpa: values.pressureKpa }),
    ...(values.gravityG === undefined ? {} : { gravity_g: values.gravityG }),
    ...(values.flowCmS === undefined ? {} : { flow_speed_cm_s: values.flowCmS }),
    ...(values.phase ? { fuel_phase: values.phase } : {}),
    ...(values.material ? { material: values.material } : {}),
  };
}

export function hasScenarioInput(values: ScenarioValues): boolean {
  return (
    Boolean(values.preset) ||
    [values.o2Percent, values.pressureKpa, values.gravityG, values.flowCmS].some(
      (value) => value !== undefined,
    )
  );
}
