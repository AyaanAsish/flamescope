import type { CriterionWeights, Lens, LensWeights } from "@/lib/api/types";
import { LENSES } from "@/lib/constants";

const PAIR_SEPARATOR = ",";
const KEY_VALUE_SEPARATOR = ":";
const LENS_CRITERION_SEPARATOR = ".";

function isLens(value: string): value is Lens {
  return (LENSES as readonly string[]).includes(value);
}

function parsePairs(raw: string | null): [string, number][] {
  if (!raw) return [];
  return raw.split(PAIR_SEPARATOR).flatMap((pair) => {
    const [key, text] = pair.split(KEY_VALUE_SEPARATOR);
    const value = Number(text);
    return key && text !== undefined && Number.isFinite(value)
      ? [[key, value] as [string, number]]
      : [];
  });
}

const roundWeight = (value: number) => Math.round(value * 1000) / 1000;

export function parseLensWeights(raw: string | null): LensWeights | null {
  const pairs = parsePairs(raw).filter(([key]) => isLens(key));
  return pairs.length ? (Object.fromEntries(pairs) as LensWeights) : null;
}

export function encodeLensWeights(weights: LensWeights | null): string | null {
  if (!weights) return null;
  const pairs = Object.entries(weights).map(
    ([lens, value]) => `${lens}${KEY_VALUE_SEPARATOR}${roundWeight(value)}`,
  );
  return pairs.length ? pairs.join(PAIR_SEPARATOR) : null;
}

export function parseCriterionWeights(raw: string | null): CriterionWeights | null {
  const result: CriterionWeights = {};
  for (const [key, value] of parsePairs(raw)) {
    const [lens, criterion] = key.split(LENS_CRITERION_SEPARATOR);
    if (!lens || !criterion || !isLens(lens)) continue;
    result[lens] = { ...result[lens], [criterion]: value };
  }
  return Object.keys(result).length ? result : null;
}

export function encodeCriterionWeights(weights: CriterionWeights | null): string | null {
  if (!weights) return null;
  const pairs = (Object.entries(weights) as [Lens, Record<string, number>][]).flatMap(
    ([lens, group]) =>
      Object.entries(group).map(
        ([criterion, value]) =>
          `${lens}${LENS_CRITERION_SEPARATOR}${criterion}${KEY_VALUE_SEPARATOR}${roundWeight(value)}`,
      ),
  );
  return pairs.length ? pairs.join(PAIR_SEPARATOR) : null;
}

/** Weights need not sum to 1; the API normalizes them, and the UI shows the resulting shares. */
export function normalizeWeights(weights: Record<string, number>): Record<string, number> {
  const total = Object.values(weights).reduce((sum, value) => sum + value, 0);
  const entries = Object.entries(weights).map(([key, value]) => [
    key,
    total > 0 ? value / total : 0,
  ]);
  return Object.fromEntries(entries);
}
