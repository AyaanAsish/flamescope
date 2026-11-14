import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  segmentsFromBreakdown,
  segmentsFromLenses,
  StackedScoreBar,
} from "@/components/charts/StackedScoreBar";
import { LENS_COLORS } from "@/lib/constants";
import { WORKED_BREAKDOWN, WORKED_SCORE } from "@/test-fixtures";

const SUM_PRECISION = 2;

function widthPercent(element: Element): number {
  return Number.parseFloat((element as HTMLElement).style.width);
}

describe("segmentsFromBreakdown (doc 08 sections 2 and 6)", () => {
  it("FR-03: the worked example contributions sum to the 72.9 lens score", () => {
    const segments = segmentsFromBreakdown(WORKED_BREAKDOWN, "habitat");
    const total = segments.reduce((sum, segment) => sum + segment.contribution, 0);
    expect(total).toBeCloseTo(WORKED_SCORE, SUM_PRECISION);
    expect(Math.round(total * 10) / 10).toBe(72.9);
  });

  it("FR-03: null criteria (no evidence) contribute no segment", () => {
    const keys = segmentsFromBreakdown(WORKED_BREAKDOWN, "habitat").map((segment) => segment.key);
    expect(keys).toEqual(["fuel_realism", "atmosphere_match", "phenomenon", "gravity_bounding"]);
  });

  it("FR-03: segments use the fixed lens colour (doc 10 section 2.1)", () => {
    const colors = new Set(segmentsFromBreakdown(WORKED_BREAKDOWN, "habitat").map((s) => s.color));
    expect([...colors]).toEqual([LENS_COLORS.habitat]);
  });
});

describe("segmentsFromLenses (doc 08 section 2, overall)", () => {
  it("FR-03: overall segments are W-weighted lens scores that sum to the overall score", () => {
    const lensScores = { habitat: 78, modeling: 64, controls: 51 };
    const weights = { habitat: 0.4, modeling: 0.3, controls: 0.3 };
    const expectedOverall = 0.4 * 78 + 0.3 * 64 + 0.3 * 51;
    const total = segmentsFromLenses(lensScores, weights).reduce(
      (sum, s) => sum + s.contribution,
      0,
    );
    expect(total).toBeCloseTo(expectedOverall, 10);
  });

  it("FR-03: lenses with a null score are left out and the weights renormalize", () => {
    const segments = segmentsFromLenses(
      { habitat: 80, modeling: null, controls: 40 },
      { habitat: 0.4, modeling: 0.3, controls: 0.3 },
    );
    expect(segments.map((segment) => segment.key)).toEqual(["habitat", "controls"]);
    const total = segments.reduce((sum, segment) => sum + segment.contribution, 0);
    expect(total).toBeCloseTo((0.4 * 80 + 0.3 * 40) / 0.7, 10);
  });
});

describe("StackedScoreBar (doc 10 section 3 charts)", () => {
  it("FR-03: renders one segment per contribution, widths summing to the score out of 100", () => {
    const segments = segmentsFromBreakdown(WORKED_BREAKDOWN, "habitat");
    render(<StackedScoreBar segments={segments} score={WORKED_SCORE} label="BASS-II" />);
    const bar = screen.getByRole("img", { name: "BASS-II score 72.9 out of 100" });
    const widths = Array.from(bar.children).map(widthPercent);
    expect(widths).toHaveLength(4);
    expect(widths.reduce((sum, width) => sum + width, 0)).toBeCloseTo(WORKED_SCORE, SUM_PRECISION);
    expect(screen.getByText("72.9")).toBeInTheDocument();
  });

  it("FR-03: segment tooltips name the criterion and its points", () => {
    const segments = segmentsFromBreakdown(WORKED_BREAKDOWN, "habitat");
    render(<StackedScoreBar segments={segments} score={WORKED_SCORE} label="BASS-II" />);
    expect(screen.getByTitle("Fuel realism: 29.4 points")).toBeInTheDocument();
  });

  it("FR-03: a null score renders an empty bar marked not available", () => {
    render(<StackedScoreBar segments={[]} score={null} label="CFI-G" />);
    const bar = screen.getByRole("img", { name: "CFI-G score n/a out of 100" });
    expect(bar.children).toHaveLength(0);
  });
});
