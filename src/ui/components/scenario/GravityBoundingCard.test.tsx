import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { GravityBoundingCard } from "@/components/scenario/GravityBoundingCard";
import { GRAVITY_BOUNDING } from "@/test-fixtures";

describe("GravityBoundingCard (doc 08 section 4.4, doc 05 section 7)", () => {
  it("FR-16: states that no partial-gravity data exists and shows the template statement", () => {
    render(<GravityBoundingCard bounding={GRAVITY_BOUNDING} />);
    const card = screen.getByTestId("gravity-bounding");
    expect(within(card).getByText("No partial-gravity data")).toBeInTheDocument();
    expect(within(card).getByText(GRAVITY_BOUNDING.statement!)).toBeInTheDocument();
  });

  it("FR-16: the lower bound is 0 g with its investigations and the upper bound is 1 g", () => {
    render(<GravityBoundingCard bounding={GRAVITY_BOUNDING} />);
    const card = screen.getByTestId("gravity-bounding");
    const lower = within(card).getByText("Lower bound").parentElement as HTMLElement;
    expect(within(lower).getByText("0 g")).toBeInTheDocument();
    expect(within(lower).getByText("BASS-II")).toBeInTheDocument();
    const upper = within(card).getByText("Upper bound").parentElement as HTMLElement;
    expect(within(upper).getByText("1 g")).toBeInTheDocument();
    expect(within(upper).getByText("No matching investigations")).toBeInTheDocument();
  });

  it("FR-16: names the partial-gravity analogue (E-FIELD Flames)", () => {
    render(<GravityBoundingCard bounding={GRAVITY_BOUNDING} />);
    expect(screen.getByText(/Analogue: E-FIELD Flames/)).toBeInTheDocument();
  });

  it("FR-16: when partial-gravity data exists the badge says so and absent bounds read n/a", () => {
    render(
      <GravityBoundingCard
        bounding={{
          partial_gravity_data: true,
          lower_bound: null,
          upper_bound: null,
          analogue: null,
          statement: null,
        }}
      />,
    );
    const card = screen.getByTestId("gravity-bounding");
    expect(within(card).getByText("Partial-gravity data present")).toBeInTheDocument();
    expect(within(card).getAllByText("n/a")).toHaveLength(2);
    expect(within(card).queryByText(/Analogue/)).not.toBeInTheDocument();
  });
});
