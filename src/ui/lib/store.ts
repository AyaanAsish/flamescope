"use client";

import { create } from "zustand";
import type { CriterionWeights, LensWeights } from "@/lib/api/types";
import { COMPARE_MAX } from "@/lib/constants";

interface UiState {
  sidebarCollapsed: boolean;
  compareSelection: string[];
  lensWeightDraft: LensWeights | null;
  criterionWeightDraft: CriterionWeights | null;
  toggleSidebar: () => void;
  toggleCompare: (acronym: string) => void;
  setCompareSelection: (acronyms: string[]) => void;
  setLensWeightDraft: (weights: LensWeights | null) => void;
  setCriterionWeightDraft: (weights: CriterionWeights | null) => void;
}

export const useUiStore = create<UiState>((set) => ({
  sidebarCollapsed: false,
  compareSelection: [],
  lensWeightDraft: null,
  criterionWeightDraft: null,
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  toggleCompare: (acronym) =>
    set((state) => {
      if (state.compareSelection.includes(acronym)) {
        return { compareSelection: state.compareSelection.filter((item) => item !== acronym) };
      }
      return { compareSelection: [...state.compareSelection, acronym].slice(-COMPARE_MAX) };
    }),
  setCompareSelection: (acronyms) => set({ compareSelection: acronyms.slice(0, COMPARE_MAX) }),
  setLensWeightDraft: (weights) => set({ lensWeightDraft: weights }),
  setCriterionWeightDraft: (weights) => set({ criterionWeightDraft: weights }),
}));
