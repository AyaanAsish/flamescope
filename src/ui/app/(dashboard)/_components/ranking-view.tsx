"use client";

import { useState } from "react";
import { EvidenceDrawer, type EvidenceSection } from "@/components/investigations/EvidenceDrawer";
import { PageHeader } from "@/components/layout/PageHeader";
import { LensTabs } from "@/components/ranking/LensTabs";
import { PresetSelect } from "@/components/ranking/PresetSelect";
import { RankTable } from "@/components/ranking/RankTable";
import { WeightSliders } from "@/components/ranking/WeightSliders";
import { Card } from "@/components/ui/card";
import { DataPanel } from "@/components/ui/panel-state";
import { SkeletonRows } from "@/components/ui/skeleton";
import { useInvestigation, useRank, useRubric } from "@/lib/api/hooks";
import type { Lens, RankItem, RankLens, RankResponse } from "@/lib/api/types";
import { LENSES, LENS_LABELS, SCORE_DISCLAIMER } from "@/lib/constants";
import { useRankingState, type RankingState } from "./use-ranking-state";

function useEvidenceSections(item: RankItem | null, lens: RankLens): EvidenceSection[] {
  const needsDetail = item !== null && lens === "overall";
  const detail = useInvestigation(needsDetail ? item.acronym : "");
  if (!item) return [];
  if (lens !== "overall")
    return [{ title: `${LENS_LABELS[lens]} criteria`, breakdown: item.breakdown }];
  return (LENSES as readonly Lens[]).flatMap((entry) => {
    const breakdown = detail.data?.score_breakdown[entry]?.breakdown;
    return breakdown ? [{ title: `${LENS_LABELS[entry]} criteria`, breakdown }] : [];
  });
}

function WeightsPanel({ state, data }: { state: RankingState; data: RankResponse }) {
  const rubric = useRubric();
  if (!rubric.data)
    return (
      <Card data-testid="ranking-weights">
        <SkeletonRows rows={4} />
      </Card>
    );
  const criterionWeights = { ...data.weights_used.criterion_weights };
  (Object.keys(state.criterionWeights ?? {}) as Lens[]).forEach((lens) => {
    criterionWeights[lens] = state.criterionWeights?.[lens] ?? criterionWeights[lens];
  });
  return (
    <WeightSliders
      lens={state.lens}
      rubric={rubric.data}
      lensWeights={{ ...data.weights_used.lens_weights, ...state.lensWeights }}
      criterionWeights={criterionWeights}
      isCustomized={state.lensWeights !== null || state.criterionWeights !== null}
      onLensWeightsChange={state.setLensWeights}
      onCriterionWeightsChange={(lens, weights) =>
        state.setCriterionWeights({ ...state.criterionWeights, [lens]: weights })
      }
      onReset={state.reset}
    />
  );
}

export function RankingView() {
  const state = useRankingState();
  const rank = useRank(state.request);
  const [selected, setSelected] = useState<RankItem | null>(null);
  const sections = useEvidenceSections(selected, state.lens);

  return (
    <>
      <PageHeader
        title="Ranking"
        description="Relative relevance of each investigation to habitat fire safety, predictive modeling and fire-safety controls. Scores are computed deterministically from curated, cited criterion ratings."
        actions={<PresetSelect preset={state.preset} onPresetChange={state.setPreset} />}
      />
      <p className="rounded-control border-line bg-surface1 text-caption text-muted mb-4 border px-4 py-2">
        {SCORE_DISCLAIMER}
      </p>
      <LensTabs lens={state.lens} onLensChange={state.setLens} />
      <div className="mt-5 grid grid-cols-1 gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
        <DataPanel
          query={rank}
          skeleton={
            <Card>
              <SkeletonRows rows={6} />
            </Card>
          }
        >
          {(data) => <WeightsPanel state={state} data={data} />}
        </DataPanel>
        <DataPanel
          query={rank}
          skeleton={<SkeletonRows rows={8} />}
          isEmpty={(data) => data.items.length === 0}
          emptyMessage="No investigations are ranked yet."
        >
          {(data) => <RankTable data={data} lens={state.lens} onSelect={setSelected} />}
        </DataPanel>
      </div>
      <EvidenceDrawer
        open={selected !== null}
        onOpenChange={(open) => !open && setSelected(null)}
        title={selected ? `${selected.acronym} evidence` : "Evidence"}
        description="Criterion ratings with the rationale and sources behind them."
        sections={sections}
      />
    </>
  );
}
