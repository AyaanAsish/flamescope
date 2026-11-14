import type { ExtractFilters, ExtractRequest, FuelPhase } from "@/lib/api/types";
import { percentToFraction } from "@/lib/format";
import { parseList, parseNumber } from "@/lib/use-url-state";

export const OUTCOME_KEYS = [
  "ignited",
  "flame_spread_rate_mm_s",
  "burn_rate",
  "extinction",
  "smoke_point",
  "cool_flame",
] as const;
export const DEFAULT_EXTRACT_LIMIT = 50;

export function readExtractRequest(params: URLSearchParams): ExtractRequest {
  const o2Min = parseNumber(params.get("o2_min"));
  const o2Max = parseNumber(params.get("o2_max"));
  const filters: ExtractFilters = {
    investigations: parseList(params.get("inv")),
    fuel_phase: parseList(params.get("phase")) as FuelPhase[],
    has_outcome: parseList(params.get("outcome")),
    o2_min: o2Min === undefined ? undefined : percentToFraction(o2Min),
    o2_max: o2Max === undefined ? undefined : percentToFraction(o2Max),
    pressure_min_kpa: parseNumber(params.get("pmin")),
    pressure_max_kpa: parseNumber(params.get("pmax")),
  };
  const columns = parseList(params.get("cols"));
  return { filters, ...(columns.length ? { columns } : {}), limit: DEFAULT_EXTRACT_LIMIT };
}
