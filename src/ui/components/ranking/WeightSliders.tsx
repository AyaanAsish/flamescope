"use client";

import { RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { normalizeWeights } from "@/components/ranking/weights";
import type { Lens, RankLens, RubricResponse } from "@/lib/api/types";
import { LENSES, LENS_LABELS } from "@/lib/constants";
import { formatScore } from "@/lib/format";

const SLIDER_MAX = 1;
const SLIDER_STEP = 0.05;
const PERCENT = 100;

interface WeightRowProps {
  label: string;
  value: number;
  share: number;
  onChange: (value: number) => void;
}

function WeightRow({ label, value, share, onChange }: WeightRowProps) {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1">
      <span className="text-muted text-sm">{label}</span>
      <span className="mono text-fg text-xs">{formatScore(share * PERCENT)} % share</span>
      <Slider
        className="col-span-2"
        label={`${label} weight`}
        value={value}
        min={0}
        max={SLIDER_MAX}
        step={SLIDER_STEP}
        onChange={onChange}
      />
    </div>
  );
}

interface WeightGroupProps {
  title: string;
  weights: Record<string, number>;
  labels: Record<string, string>;
  onChange: (weights: Record<string, number>) => void;
}

function WeightGroup({ title, weights, labels, onChange }: WeightGroupProps) {
  const shares = normalizeWeights(weights);
  return (
    <div className="space-y-3">
      <h3 className="text-muted text-xs font-medium tracking-wide uppercase">{title}</h3>
      {Object.entries(weights).map(([id, value]) => (
        <WeightRow
          key={id}
          label={labels[id] ?? id}
          value={value}
          share={shares[id] ?? 0}
          onChange={(next) => onChange({ ...weights, [id]: next })}
        />
      ))}
    </div>
  );
}

interface WeightSlidersProps {
  lens: RankLens;
  rubric: RubricResponse;
  lensWeights: Record<Lens, number>;
  criterionWeights: Record<Lens, Record<string, number>>;
  isCustomized: boolean;
  onLensWeightsChange: (weights: Record<Lens, number>) => void;
  onCriterionWeightsChange: (lens: Lens, weights: Record<string, number>) => void;
  onReset: () => void;
}

export function WeightSliders(props: WeightSlidersProps) {
  const { lens, rubric, lensWeights, criterionWeights } = props;
  const lensLabels = Object.fromEntries(LENSES.map((item) => [item, LENS_LABELS[item]]));
  const visibleLenses = lens === "overall" ? [] : [lens];
  return (
    <Card data-testid="ranking-weights" className="space-y-5">
      <CardHeader
        title="Weights"
        description="Weights are normalized; only their ratios matter."
        action={
          <Button size="sm" variant="ghost" disabled={!props.isCustomized} onClick={props.onReset}>
            <RotateCcw className="size-3.5" aria-hidden /> Reset
          </Button>
        }
      />
      <WeightGroup
        title="Lens weights (overall)"
        weights={lensWeights}
        labels={lensLabels}
        onChange={(next) => props.onLensWeightsChange(next as Record<Lens, number>)}
      />
      {visibleLenses.map((item) => (
        <WeightGroup
          key={item}
          title={`${LENS_LABELS[item]} criteria`}
          weights={criterionWeights[item] ?? {}}
          labels={Object.fromEntries(
            rubric.lenses[item].criteria.map((criterion) => [criterion.id, criterion.label]),
          )}
          onChange={(next) => props.onCriterionWeightsChange(item, next)}
        />
      ))}
      {lens === "overall" ? (
        <p className="text-caption text-muted">Select a lens to tune its criterion weights.</p>
      ) : null}
    </Card>
  );
}
