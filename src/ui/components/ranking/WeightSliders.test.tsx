import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WeightSliders } from "@/components/ranking/WeightSliders";
import { normalizeWeights } from "@/components/ranking/weights";
import type { Lens, RankLens } from "@/lib/api/types";
import { RANK, RUBRIC } from "@/test-fixtures";

const DEFAULT_LENS_WEIGHTS = RUBRIC.lens_weights;
const CRITERION_WEIGHTS = RANK.weights_used.criterion_weights;
const SLIDER_STEP = 0.05;

function renderSliders(lens: RankLens, lensWeights: Record<Lens, number> = DEFAULT_LENS_WEIGHTS) {
  const callbacks = {
    onLensWeightsChange: vi.fn(),
    onCriterionWeightsChange: vi.fn(),
    onReset: vi.fn(),
  };
  render(
    <WeightSliders
      lens={lens}
      rubric={RUBRIC}
      lensWeights={lensWeights}
      criterionWeights={CRITERION_WEIGHTS}
      isCustomized
      {...callbacks}
    />,
  );
  return callbacks;
}

describe("normalizeWeights (doc 05 section 5: weights need not sum to 1)", () => {
  it("FR-04: divides each weight by the total", () => {
    expect(normalizeWeights({ habitat: 2, modeling: 1, controls: 1 })).toEqual({
      habitat: 0.5,
      modeling: 0.25,
      controls: 0.25,
    });
  });

  it("FR-04: weights that already sum to 1 are unchanged and shares always sum to 1", () => {
    const shares = normalizeWeights({ habitat: 0.6, modeling: 0.2, controls: 0.2 });
    expect(shares.habitat).toBeCloseTo(0.6, 10);
    const total = Object.values(normalizeWeights({ a: 0.3, b: 0.9, c: 0.15 })).reduce(
      (x, y) => x + y,
    );
    expect(total).toBeCloseTo(1, 10);
  });

  it("FR-04: all-zero weights give zero shares instead of dividing by zero", () => {
    expect(normalizeWeights({ habitat: 0, modeling: 0 })).toEqual({ habitat: 0, modeling: 0 });
  });
});

describe("WeightSliders (doc 10 section 5 /ranking, CF-05)", () => {
  it("FR-04: shows the normalized share of each lens weight with a unit", () => {
    renderSliders("overall", { habitat: 2, modeling: 1, controls: 1 });
    expect(screen.getByTestId("ranking-weights")).toBeInTheDocument();
    expect(screen.getByText("50 % share")).toBeInTheDocument();
    expect(screen.getAllByText("25 % share")).toHaveLength(2);
  });

  it("FR-04: the default rubric lens weights show 40 / 30 / 30 percent", () => {
    renderSliders("overall");
    expect(screen.getByText("40 % share")).toBeInTheDocument();
    expect(screen.getAllByText("30 % share")).toHaveLength(2);
    expect(screen.queryByText("Habitat criteria")).not.toBeInTheDocument();
  });

  it("FR-04: moving a lens slider reports the new lens weights", () => {
    const callbacks = renderSliders("overall");
    fireEvent.keyDown(screen.getByRole("slider", { name: "Habitat weight" }), {
      key: "ArrowRight",
    });
    expect(callbacks.onLensWeightsChange).toHaveBeenCalledWith({
      ...DEFAULT_LENS_WEIGHTS,
      habitat: DEFAULT_LENS_WEIGHTS.habitat + SLIDER_STEP,
    });
  });

  it("FR-04: a selected lens shows its five rubric criteria and reports criterion changes", () => {
    const callbacks = renderSliders("habitat");
    const criteria = RUBRIC.lenses.habitat.criteria;
    criteria.forEach((criterion) =>
      expect(screen.getByRole("slider", { name: `${criterion.label} weight` })).toBeInTheDocument(),
    );
    fireEvent.keyDown(screen.getByRole("slider", { name: "Fuel realism weight" }), {
      key: "ArrowLeft",
    });
    expect(callbacks.onCriterionWeightsChange).toHaveBeenCalledWith("habitat", {
      ...CRITERION_WEIGHTS.habitat,
      fuel_realism: CRITERION_WEIGHTS.habitat.fuel_realism! - SLIDER_STEP,
    });
  });

  it("FR-04: Reset calls back when the weights are customized", () => {
    const callbacks = renderSliders("overall");
    fireEvent.click(screen.getByRole("button", { name: /reset/i }));
    expect(callbacks.onReset).toHaveBeenCalledTimes(1);
  });
});
