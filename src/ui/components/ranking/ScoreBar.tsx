import {
  segmentsFromBreakdown,
  segmentsFromLenses,
  StackedScoreBar,
} from "@/components/charts/StackedScoreBar";
import type { Lens, RankItem, RankLens } from "@/lib/api/types";

interface ScoreBarProps {
  item: RankItem;
  lens: RankLens;
  lensWeights: Record<Lens, number>;
}

function segmentsFor({ item, lens, lensWeights }: ScoreBarProps) {
  return lens === "overall"
    ? segmentsFromLenses(item.lens_scores, lensWeights)
    : segmentsFromBreakdown(item.breakdown, lens);
}

/** Ranking score bar: the overall lens stacks lens contributions, a single lens stacks its criteria. */
export function ScoreBar(props: ScoreBarProps) {
  return (
    <StackedScoreBar
      segments={segmentsFor(props)}
      score={props.item.score}
      label={props.item.acronym}
    />
  );
}
