import type { OpenRangePair } from "@/lib/api/types";
import { humanize } from "@/lib/utils";

export type PressureUnit = "kPa" | "psi";

export const KPA_PER_PSI = 6.894757;
const PERCENT = 100;
const BYTES_PER_KB = 1024;
const EMPTY = "n/a";

export function fractionToPercent(fraction: number): number {
  return fraction * PERCENT;
}

export function percentToFraction(percent: number): number {
  return percent / PERCENT;
}

export function kpaToPsi(kpa: number): number {
  return kpa / KPA_PER_PSI;
}

export function psiToKpa(psi: number): number {
  return psi * KPA_PER_PSI;
}

export function roundTo(value: number, digits: number): number {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

function formatNumber(value: number, digits: number): string {
  return roundTo(value, digits).toLocaleString("en-US", { maximumFractionDigits: digits });
}

export function formatOxygen(fraction: number | null | undefined): string {
  if (fraction === null || fraction === undefined) return EMPTY;
  return `${formatNumber(fractionToPercent(fraction), 1)} % O₂`;
}

export function formatPressure(kpa: number | null | undefined, unit: PressureUnit = "kPa"): string {
  if (kpa === null || kpa === undefined) return EMPTY;
  return unit === "psi" ? `${formatNumber(kpaToPsi(kpa), 1)} psi` : `${formatNumber(kpa, 1)} kPa`;
}

export function formatFlow(cmPerSecond: number | null | undefined): string {
  if (cmPerSecond === null || cmPerSecond === undefined) return EMPTY;
  return `${formatNumber(cmPerSecond, 1)} cm/s`;
}

export function formatGravity(gravityG: number | null | undefined): string {
  if (gravityG === null || gravityG === undefined) return EMPTY;
  return `${formatNumber(gravityG, 3)} g`;
}

export function formatSpreadRate(mmPerSecond: number | null | undefined): string {
  if (mmPerSecond === null || mmPerSecond === undefined) return EMPTY;
  return `${formatNumber(mmPerSecond, 2)} mm/s`;
}

type RangeInput = OpenRangePair | null | undefined;

/** A half-open range is shown as a bound, never as a point (doc 04 s2). */
function formatRange(range: RangeInput, format: (value: number) => string): string {
  if (!range) return EMPTY;
  const [low, high] = range;
  if (low === null) return high === null ? EMPTY : `≤ ${format(high)}`;
  if (high === null) return `≥ ${format(low)}`;
  return low === high ? format(low) : `${format(low)} – ${format(high)}`;
}

export function formatOxygenRange(range: RangeInput): string {
  return formatRange(range, (value) => `${formatNumber(fractionToPercent(value), 1)} %`);
}

export function formatPressureRange(range: RangeInput, unit: PressureUnit = "kPa"): string {
  return formatRange(range, (value) => formatPressure(value, unit));
}

export function formatFlowRange(range: RangeInput): string {
  return formatRange(range, formatFlow);
}

export function formatScore(score: number | null | undefined): string {
  return score === null || score === undefined ? EMPTY : formatNumber(score, 1);
}

export function formatConfidence(confidence: number | null | undefined): string {
  if (confidence === null || confidence === undefined) return EMPTY;
  return `${formatNumber(fractionToPercent(confidence), 0)} %`;
}

export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return EMPTY;
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unitIndex = 0;
  while (value >= BYTES_PER_KB && unitIndex < units.length - 1) {
    value /= BYTES_PER_KB;
    unitIndex += 1;
  }
  return `${formatNumber(value, 1)} ${units[unitIndex]}`;
}

export function formatCount(count: number): string {
  return count.toLocaleString("en-US");
}

export function formatTimestamp(iso: string | null | undefined): string {
  if (!iso) return EMPTY;
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? EMPTY
    : date.toISOString().slice(0, 16).replace("T", " ") + " UTC";
}

export function formatCell(value: unknown): string {
  if (value === null || value === undefined) return EMPTY;
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "number") return formatNumber(value, 4);
  if (Array.isArray(value)) return value.map(formatCell).join(", ");
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

export function formatLabel(identifier: string): string {
  return humanize(identifier);
}

export const NOT_AVAILABLE = EMPTY;
