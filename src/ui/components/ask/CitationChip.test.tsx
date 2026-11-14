import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CitationChip } from "@/components/ask/CitationChip";
import { SOURCE } from "@/test-fixtures";

describe("CitationChip (doc 10 section 5 /ask, FR-15 provenance)", () => {
  it("FR-15: renders the citation number under the citation-chip test ID", () => {
    render(<CitationChip index={2} source={SOURCE} isActive={false} onSelect={vi.fn()} />);
    const chip = screen.getByTestId("citation-chip");
    expect(chip).toHaveTextContent("2");
    expect(chip).toHaveAttribute("aria-pressed", "false");
  });

  it("FR-15: the tooltip shows the cited quote, falling back to title and URI", () => {
    const { rerender } = render(
      <CitationChip index={1} source={SOURCE} isActive={false} onSelect={vi.fn()} />,
    );
    expect(screen.getByTestId("citation-chip")).toHaveAttribute("title", SOURCE.quote);
    rerender(
      <CitationChip
        index={1}
        source={{ ...SOURCE, quote: null }}
        isActive={false}
        onSelect={vi.fn()}
      />,
    );
    expect(screen.getByTestId("citation-chip")).toHaveAttribute("title", SOURCE.title);
    rerender(
      <CitationChip
        index={1}
        source={{ kind: "s3_object", uri: "s3://nasa-psi/a.pdf" }}
        isActive={false}
        onSelect={vi.fn()}
      />,
    );
    expect(screen.getByTestId("citation-chip")).toHaveAttribute("title", "s3://nasa-psi/a.pdf");
  });

  it("FR-11: clicking selects the source so the source panel can open it", () => {
    const onSelect = vi.fn();
    render(<CitationChip index={1} source={SOURCE} isActive={false} onSelect={onSelect} />);
    fireEvent.click(screen.getByTestId("citation-chip"));
    expect(onSelect).toHaveBeenCalledWith(SOURCE);
  });

  it("FR-11: the active chip is announced as pressed, not only coloured", () => {
    render(<CitationChip index={1} source={SOURCE} isActive onSelect={vi.fn()} />);
    expect(screen.getByTestId("citation-chip")).toHaveAttribute("aria-pressed", "true");
  });
});
