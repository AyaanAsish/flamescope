import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { InvestigationCard } from "@/components/investigations/InvestigationCard";
import type { InvestigationSummary } from "@/lib/api/types";
import { BASS_II } from "@/test-fixtures";

function renderCard(investigation: InvestigationSummary = BASS_II, isSelected = false) {
  const onToggleCompare = vi.fn();
  render(
    <InvestigationCard
      investigation={investigation}
      isSelectedForCompare={isSelected}
      onToggleCompare={onToggleCompare}
    />,
  );
  return { card: screen.getByTestId("investigation-card"), onToggleCompare };
}

describe("InvestigationCard (doc 05 section 4 InvestigationSummary, doc 10 section 5 /explorer)", () => {
  it("FR-01: shows acronym, title and a link to the detail route", () => {
    const { card } = renderCard();
    expect(card).toHaveAttribute("data-acronym", "BASS-II");
    expect(within(card).getByRole("link", { name: "BASS-II" })).toHaveAttribute(
      "href",
      "/investigations/BASS-II",
    );
    expect(within(card).getByText(BASS_II.title)).toBeInTheDocument();
  });

  it("FR-01: condition ranges carry units with oxygen as percent", () => {
    const { card } = renderCard();
    expect(within(card).getByText("14 % – 21 %")).toBeInTheDocument();
    expect(within(card).getByText("101.3 kPa")).toBeInTheDocument();
    expect(within(card).getByText("1 cm/s – 55 cm/s")).toBeInTheDocument();
  });

  it("FR-03: shows the three lens scores and the overall score", () => {
    const { card } = renderCard();
    ["Habitat", "Modeling", "Controls", "Overall"].forEach((label) =>
      expect(within(card).getByText(label)).toBeInTheDocument(),
    );
    ["78", "64", "51", "66"].forEach((score) =>
      expect(within(card).getByText(score)).toBeInTheDocument(),
    );
  });

  it("FR-01: badges show fuel phase, platform, gravity and review state as text", () => {
    const { card } = renderCard();
    expect(within(card).getByText("Solid")).toBeInTheDocument();
    expect(within(card).getByText("ISS")).toBeInTheDocument();
    expect(within(card).getByText("Microgravity")).toBeInTheDocument();
    expect(within(card).getByText("Reviewed")).toBeInTheDocument();
  });

  it("FR-15: unknown values read not available and a missing summary is stated", () => {
    const unknown: InvestigationSummary = {
      ...BASS_II,
      summary: null,
      reviewed: false,
      o2_range: null,
      pressure_range_kpa: null,
      flow_range_cm_s: null,
      scores: { habitat: null, modeling: null, controls: null, overall: null },
    };
    const { card } = renderCard(unknown);
    expect(within(card).getByText("No curated summary yet.")).toBeInTheDocument();
    expect(within(card).getByText("Unreviewed")).toBeInTheDocument();
    expect(within(card).getAllByText("n/a")).toHaveLength(7);
  });

  it("FR-05: the compare toggle reports the acronym and reflects the selection", () => {
    const { card, onToggleCompare } = renderCard();
    const toggle = within(card).getByRole("button", { name: /add to compare/i });
    expect(toggle).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(toggle);
    expect(onToggleCompare).toHaveBeenCalledWith("BASS-II");
  });

  it("FR-05: a selected card says so in text, not only by colour", () => {
    const { card } = renderCard(BASS_II, true);
    const toggle = within(card).getByRole("button", { name: /selected for compare/i });
    expect(toggle).toHaveAttribute("aria-pressed", "true");
  });
});
