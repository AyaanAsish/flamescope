"use client";

import { useEffect, useEffectEvent } from "react";
import {
  encodeCriterionWeights,
  encodeLensWeights,
  parseCriterionWeights,
  parseLensWeights,
} from "@/components/ranking/weights";
import type { CriterionWeights, LensWeights, RankLens, RankRequest } from "@/lib/api/types";
import { RANK_LENSES, SLIDER_DEBOUNCE_MS } from "@/lib/constants";
import { useUiStore } from "@/lib/store";
import { useDebouncedValue, useUrlState } from "@/lib/use-url-state";

// The doc 05 s1 maximum, so every investigation in the catalog is ranked (FR-03).
const RANK_LIMIT = 100;

function parseLens(raw: string | null): RankLens {
  return RANK_LENSES.find((lens) => lens === raw) ?? "overall";
}

export interface RankingState {
  lens: RankLens;
  preset: string;
  lensWeights: LensWeights | null;
  criterionWeights: CriterionWeights | null;
  request: RankRequest;
  setLens: (lens: RankLens) => void;
  setPreset: (preset: string) => void;
  setLensWeights: (weights: LensWeights) => void;
  setCriterionWeights: (weights: CriterionWeights) => void;
  reset: () => void;
}

/** URL holds the committed state; the store holds slider drafts, debounced into the URL. */
export function useRankingState(): RankingState {
  const { params, patch } = useUrlState();
  const draftLens = useUiStore((state) => state.lensWeightDraft);
  const draftCriteria = useUiStore((state) => state.criterionWeightDraft);
  const setDraftLens = useUiStore((state) => state.setLensWeightDraft);
  const setDraftCriteria = useUiStore((state) => state.setCriterionWeightDraft);

  const lens = parseLens(params.get("lens"));
  const preset = params.get("preset") ?? "";
  const lensWeights = draftLens ?? parseLensWeights(params.get("lw"));
  const criterionWeights = draftCriteria ?? parseCriterionWeights(params.get("cw"));

  const committed = useDebouncedValue({ lensWeights, criterionWeights }, SLIDER_DEBOUNCE_MS);
  const hasDraft = draftLens !== null || draftCriteria !== null;
  const committedKey = JSON.stringify(committed);
  const mirrorToUrl = useEffectEvent(() => {
    if (!hasDraft) return;
    patch({
      lw: encodeLensWeights(committed.lensWeights),
      cw: encodeCriterionWeights(committed.criterionWeights),
    });
  });

  useEffect(() => {
    mirrorToUrl();
  }, [committedKey]);

  const clearDrafts = () => {
    setDraftLens(null);
    setDraftCriteria(null);
  };

  const request: RankRequest = {
    lens,
    limit: RANK_LIMIT,
    ...(preset ? { preset } : {}),
    ...(committed.lensWeights ? { lens_weights: committed.lensWeights } : {}),
    ...(committed.criterionWeights ? { criterion_weights: committed.criterionWeights } : {}),
  };

  return {
    lens,
    preset,
    lensWeights,
    criterionWeights,
    request,
    setLens: (next) => patch({ lens: next === "overall" ? null : next }),
    setPreset: (next) => {
      clearDrafts();
      patch({ preset: next, lw: null, cw: null });
    },
    setLensWeights: setDraftLens,
    setCriterionWeights: setDraftCriteria,
    reset: () => {
      clearDrafts();
      patch({ lw: null, cw: null });
    },
  };
}
