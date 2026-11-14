import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DiffMatrix, formatMatrixValue } from "@/components/compare/DiffMatrix";
import { COMPARE } from "@/test-fixtures";

const ACRONYMS = ["BASS-II", "FLEX-2"];

function rowFor(attributeLabel: string): HTMLElement {
  return screen.getByText(attributeLabel).closest("tr") as HTMLElement;
}

describe("DiffMatrix (doc 05 section 6, doc 10 section 5 /compare)", () => {
  it("FR-05: renders the rows in the order the API returns them, under the diff-matrix test ID", () => {
    render(<DiffMatrix rows={COMPARE.matrix} acronyms={ACRONYMS} />);
    const matrix = screen.getByTestId("diff-matrix");
    const labels = within(matrix)
      .getAllByRole("row")
      .slice(1)
      .map((row) => row.querySelector("td")?.firstChild?.textContent);
    expect(labels).toEqual(COMPARE.matrix.map((row) => row.label));
    ACRONYMS.forEach((acronym) =>
      expect(within(matrix).getByRole("columnheader", { name: acronym })).toBeInTheDocument(),
    );
  });

  it("FR-05: a same row carries the text Same and an icon, not colour alone", () => {
    render(<DiffMatrix rows={COMPARE.matrix} acronyms={ACRONYMS} />);
    const row = rowFor("Platform");
    expect(row).toHaveAttribute("data-same", "true");
    const marker = within(row).getByText("Same");
    expect(marker.querySelector("svg")).not.toBeNull();
  });

  it("FR-05: a different row carries the text Different and a distinct icon, not colour alone", () => {
    render(<DiffMatrix rows={COMPARE.matrix} acronyms={ACRONYMS} />);
    const row = rowFor("Fuel phase");
    expect(row).toHaveAttribute("data-same", "false");
    const marker = within(row).getByText("Different");
    const differentIcon = marker.querySelector("svg")?.getAttribute("class");
    const sameIcon = within(rowFor("Platform"))
      .getByText("Same")
      .querySelector("svg")
      ?.getAttribute("class");
    expect(differentIcon).toBeTruthy();
    expect(differentIcon).not.toEqual(sameIcon);
  });

  it("FR-05: values carry units; oxygen ranges are shown as percent (doc 10 section 2.3 rule 4)", () => {
    render(<DiffMatrix rows={COMPARE.matrix} acronyms={ACRONYMS} />);
    expect(within(rowFor("Oxygen range")).getAllByText("14 % – 21 %")).toHaveLength(2);
    expect(formatMatrixValue("pressure_range_kpa", [70, 101.3])).toBe("70 kPa – 101.3 kPa");
    expect(formatMatrixValue("flow_range_cm_s", [1, 55])).toBe("1 cm/s – 55 cm/s");
  });

  it("FR-15: a missing value is shown as not available", () => {
    expect(formatMatrixValue("project", null)).toBe("n/a");
    expect(formatMatrixValue("project", undefined)).toBe("n/a");
    expect(formatMatrixValue("hardware", ["MSG", "CIR"])).toBe("MSG, CIR");
  });
});
