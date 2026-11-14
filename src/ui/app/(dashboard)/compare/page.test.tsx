import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ComparePage from "@/app/(dashboard)/compare/page";
import { apiPost } from "@/lib/api/client";
import { BASS_II, COMPARE, FLEX_2, LINEAGE, pageOf } from "@/test-fixtures";
import {
  apiFailure,
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

/** CF-06 requests plus the picker catalog. */
const ROUTES = ["POST /compare", "GET /hardware", "GET /investigations"];
const DATA = {
  "POST /compare": COMPARE,
  "GET /hardware": LINEAGE,
  "GET /investigations": pageOf([BASS_II, FLEX_2]),
};
const SELECTED = "/compare?ids=BASS-II,FLEX-2";

function renderPage() {
  const { container } = renderWithQuery(<ComparePage />);
  return () => container as HTMLElement;
}

describe("Compare page /compare (doc 10 section 5, CF-06)", () => {
  it("FR-05: shows the matrix and narrative skeletons while loading", async () => {
    setUrl(SELECTED);
    serveApi(serveAll(ROUTES, PENDING));
    await findPanelState(renderPage(), "loading");
    expect(within(screen.getByTestId("compare-narrative")).getByRole("status")).toBeInTheDocument();
  });

  it("FR-05: shows the empty state when the matrix has no rows", async () => {
    setUrl(SELECTED);
    serveApi({ ...DATA, "POST /compare": { ...COMPARE, matrix: [] } });
    await findPanelState(renderPage(), "empty");
  });

  it("FR-05: a failed compare shows an error with retry and the narrative becomes unavailable", async () => {
    setUrl(SELECTED);
    serveApi({ ...DATA, "POST /compare": apiFailure(502, "LLM provider failed") });
    await findPanelState(renderPage(), "error");
    const narrative = screen.getByTestId("compare-narrative");
    await within(narrative).findByText(/language model is unavailable/);
  });

  it("FR-05: data state exposes picker, matrix, narrative and lineage under doc 10 test IDs", async () => {
    setUrl(SELECTED);
    serveApi(DATA);
    await findPanelState(renderPage(), "data");
    expect(screen.getByTestId("compare-picker")).toBeInTheDocument();
    expect(screen.getByTestId("compare-add")).toHaveAttribute("id", "compare-add");
    const matrix = await screen.findByTestId("diff-matrix");
    expect(within(matrix).getByText("Different")).toBeInTheDocument();
    expect(within(matrix).getAllByText("Same").length).toBeGreaterThan(0);
    const narrative = screen.getByTestId("compare-narrative");
    expect(within(narrative).getAllByText("Both ran on the ISS.").length).toBeGreaterThan(0);
    expect(within(narrative).getByRole("link", { name: /BASS-II overview/ })).toBeInTheDocument();
    expect(screen.getByTestId("lineage-graph")).toBeInTheDocument();
  });

  it("FR-05: asks first without and then with the narrative (CF-06)", async () => {
    setUrl(SELECTED);
    serveApi(DATA);
    renderPage();
    await waitFor(() => expect(vi.mocked(apiPost)).toHaveBeenCalledTimes(2));
    const bodies = vi.mocked(apiPost).mock.calls.map(([, body]) => body);
    expect(bodies).toEqual([
      { investigations: ["BASS-II", "FLEX-2"], narrative: false },
      { investigations: ["BASS-II", "FLEX-2"], narrative: true },
    ]);
  });

  it("FR-05: with fewer than two investigations no compare request is sent", async () => {
    setUrl("/compare?ids=BASS-II");
    serveApi(DATA);
    renderPage();
    expect(await screen.findByTestId("diff-matrix")).toHaveTextContent(/at least 2 investigations/);
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
  });
});
