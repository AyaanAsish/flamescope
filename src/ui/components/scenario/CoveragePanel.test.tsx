import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CoveragePanel } from "@/components/scenario/CoveragePanel";
import type { CoverageState } from "@/lib/api/types";
import { SCENARIO } from "@/test-fixtures";

/** Coverage states of doc 08 section 4.3 with their UI labels. */
const STATE_LABELS: [CoverageState, string][] = [
  ["covered", "Covered"],
  ["extrapolated", "Extrapolated"],
  ["no_data", "No data"],
];

function renderPanel(unit: "kPa" | "psi" = "kPa") {
  render(<CoveragePanel coverage={SCENARIO.coverage} scenario={SCENARIO.scenario} unit={unit} />);
  return screen.getByTestId("coverage-panel");
}

function rowsIn(panel: HTMLElement, state: CoverageState): HTMLElement[] {
  return Array.from(panel.querySelectorAll<HTMLElement>(`[data-state="${state}"]`));
}

describe("CoveragePanel (doc 08 section 4.3, doc 10 section 5 /scenario)", () => {
  it.each(STATE_LABELS)(
    "FR-07: state %s shows the label %s together with an icon",
    (state, label) => {
      const panel = renderPanel();
      const [row] = rowsIn(panel, state);
      expect(row).toBeDefined();
      const chip = within(row!).getByText(label);
      expect(chip.querySelector("svg")).not.toBeNull();
    },
  );

  it("FR-07: each state has its own icon, so meaning never depends on colour alone", () => {
    const panel = renderPanel();
    const iconClasses = STATE_LABELS.map(([state, label]) => {
      const chip = within(rowsIn(panel, state)[0]!).getByText(label);
      return chip.querySelector("svg")?.getAttribute("class");
    });
    expect(new Set(iconClasses).size).toBe(STATE_LABELS.length);
  });

  it("FR-07: one row per scenario dimension with units; oxygen as percent", () => {
    const panel = renderPanel();
    expect(within(panel).getByText("34 % O₂")).toBeInTheDocument();
    expect(within(panel).getByText("56.5 kPa")).toBeInTheDocument();
    expect(within(panel).getByText("10 cm/s")).toBeInTheDocument();
    expect(within(panel).getByText("0.166 g")).toBeInTheDocument();
    expect(within(panel).getByText("Catalog 10 % O₂ to 85 % O₂")).toBeInTheDocument();
  });

  it("FR-16: gravity lists the catalog gravity values instead of a range", () => {
    const panel = renderPanel();
    expect(within(panel).getByText("Catalog values: 0 g, 1 g")).toBeInTheDocument();
  });

  it("FR-07: the psi toggle converts the pressure display (56.5 kPa is 8.2 psi, doc 08 section 4.1)", () => {
    const panel = renderPanel("psi");
    expect(within(panel).getByText("8.2 psi")).toBeInTheDocument();
  });
});
