import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RankingPage from "@/app/(dashboard)/ranking/page";
import { apiPost } from "@/lib/api/client";
import { SCORE_DISCLAIMER } from "@/lib/constants";
import { useUiStore } from "@/lib/store";
import { PRESETS, RANK, RUBRIC } from "@/test-fixtures";
import {
  apiFailure,
  currentSearch,
  findPanelState,
  PENDING,
  renderWithQuery,
  serveAll,
  serveApi,
  setUrl,
} from "@/test-utils";

vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/client")>()),
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

/** CF-05 requests. */
const ROUTES = ["POST /rank", "GET /meta/rubric", "GET /meta/presets"];
const DATA = { "POST /rank": RANK, "GET /meta/rubric": RUBRIC, "GET /meta/presets": PRESETS };

function renderPage() {
  const { container } = renderWithQuery(<RankingPage />);
  return () => container as HTMLElement;
}

beforeEach(() => {
  useUiStore.setState({ lensWeightDraft: null, criterionWeightDraft: null });
});

describe("Ranking page /ranking (doc 10 section 5, CF-05)", () => {
  it("FR-03: shows skeletons while the ranking loads, with the disclaimer always visible", async () => {
    serveApi(serveAll(ROUTES, PENDING));
    const page = renderPage();
    await findPanelState(page, "loading");
    expect(screen.getByText(SCORE_DISCLAIMER)).toBeInTheDocument();
    expect(screen.getByTestId("ranking-lens-tabs")).toBeInTheDocument();
    expect(screen.getByTestId("ranking-preset")).toBeInTheDocument();
  });

  it("FR-03: shows the empty state when nothing is ranked", async () => {
    serveApi({ ...DATA, "POST /rank": { ...RANK, items: [] } });
    await findPanelState(renderPage(), "empty");
  });

  it("FR-03: shows an error with retry when /rank fails", async () => {
    serveApi({ ...DATA, "POST /rank": apiFailure(502, "Ranking failed") });
    const panel = await findPanelState(renderPage(), "error");
    expect(within(panel).getAllByRole("button", { name: "Retry" }).length).toBeGreaterThan(0);
  });

  it("FR-03: data state exposes rank-row, ranking-weights, lens tabs and preset select", async () => {
    setUrl("/ranking?lens=habitat");
    serveApi(DATA);
    await findPanelState(renderPage(), "data");
    const row = await screen.findByTestId("rank-row");
    expect(row).toHaveAttribute("data-acronym", "BASS-II");
    expect(within(row).getAllByText("72.9").length).toBeGreaterThan(0);
    expect(within(row).getByText("85 %")).toBeInTheDocument();
    expect(await screen.findByTestId("ranking-weights")).toBeInTheDocument();
    expect(screen.getByTestId("ranking-lens-tabs")).toBeInTheDocument();
    expect(screen.getByTestId("ranking-preset")).toHaveAttribute("id", "ranking-preset");
  });

  it("FR-15: the evidence drawer opens from a row and shows rationale and source links", async () => {
    setUrl("/ranking?lens=habitat");
    serveApi(DATA);
    renderPage();
    const row = await screen.findByTestId("rank-row");
    fireEvent.click(within(row).getByRole("button", { name: "Evidence" }));
    const drawer = await screen.findByTestId("evidence-drawer");
    expect(within(drawer).getByText("Fuel realism rationale")).toBeInTheDocument();
    expect(
      within(drawer).getAllByRole("link", { name: /BASS-II overview/ }).length,
    ).toBeGreaterThan(0);
    expect(within(drawer).getByText("no evidence")).toBeInTheDocument();
  });

  it("FR-04: lens, preset and URL state drive the /rank request", async () => {
    setUrl("/ranking?lens=modeling&preset=lunar_habitat");
    serveApi(DATA);
    renderPage();
    await screen.findByTestId("rank-row");
    expect(vi.mocked(apiPost)).toHaveBeenCalledWith(
      "/rank",
      expect.objectContaining({ lens: "modeling", preset: "lunar_habitat" }),
    );
  });

  it("FR-04: choosing a preset mirrors it into the URL", async () => {
    serveApi(DATA);
    renderPage();
    const select = await screen.findByTestId("ranking-preset");
    await waitFor(() => expect(select).not.toBeDisabled());
    fireEvent.change(select, { target: { value: "lunar_habitat" } });
    await waitFor(() => expect(currentSearch().get("preset")).toBe("lunar_habitat"));
  });
});
