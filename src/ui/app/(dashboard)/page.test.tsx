import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import OverviewPage from "@/app/(dashboard)/page";
import { apiGet } from "@/lib/api/client";
import { GAPS, RANK, SCATTER_TABLE, STATS } from "@/test-fixtures";
import {
  apiFailure,
  findPanelState,
  PENDING,
  renderWithQuery,
  serveAll,
  serveApi,
} from "@/test-utils";

vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/client")>()),
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

/** CF-11: the four parallel Overview requests. */
const ROUTES = ["GET /meta/stats", "POST /rank", "GET /insights/gaps", "POST /extract/preview"];
const PANELS = ["overview-stats", "overview-scatter", "overview-top", "overview-gaps"];
const LIST_PANELS = ["overview-scatter", "overview-top", "overview-gaps"];

const DATA = {
  "GET /meta/stats": STATS,
  "POST /rank": { ...RANK, lens: "overall" },
  "GET /insights/gaps": GAPS,
  "POST /extract/preview": SCATTER_TABLE,
};

describe("Overview page / (doc 10 section 5, CF-11)", () => {
  it("FR-14: every panel shows its loading skeleton while requests are pending", async () => {
    serveApi(serveAll(ROUTES, PENDING));
    renderWithQuery(<OverviewPage />);
    for (const panel of PANELS) await findPanelState(panel, "loading");
  });

  it("FR-14: list panels show their empty state when the catalog is empty", async () => {
    serveApi({
      "GET /meta/stats": { ...STATS, investigations: 0 },
      "POST /rank": { ...RANK, items: [] },
      "GET /insights/gaps": { gaps: [] },
      "POST /extract/preview": { ...SCATTER_TABLE, rows: [], total: 0 },
    });
    renderWithQuery(<OverviewPage />);
    for (const panel of LIST_PANELS) await findPanelState(panel, "empty");
  });

  it("FR-14: each panel shows its own error with a retry that refetches", async () => {
    serveApi(serveAll(ROUTES, apiFailure()));
    renderWithQuery(<OverviewPage />);
    for (const panel of PANELS) await findPanelState(panel, "error");
    const calls = vi.mocked(apiGet).mock.calls.length;
    fireEvent.click(
      within(screen.getByTestId("overview-stats")).getByRole("button", { name: "Retry" }),
    );
    await waitFor(() => expect(vi.mocked(apiGet).mock.calls.length).toBeGreaterThan(calls));
  });

  it("FR-14: data state shows stats, top investigations and gaps under the doc 10 test IDs", async () => {
    serveApi(DATA);
    renderWithQuery(<OverviewPage />);
    for (const panel of PANELS) await findPanelState(panel, "data");
    expect(within(screen.getByTestId("overview-stats")).getByText("24")).toBeInTheDocument();
    const top = screen.getByTestId("overview-top");
    expect(within(top).getByRole("link", { name: "BASS-II" })).toHaveAttribute(
      "href",
      "/investigations/BASS-II",
    );
    expect(within(top).getByText("72.9")).toBeInTheDocument();
    expect(
      within(screen.getByTestId("overview-gaps")).getByText("No partial-gravity data"),
    ).toBeInTheDocument();
  });

  it("FR-14: one failing request does not blank the other panels (CF-11)", async () => {
    serveApi({ ...DATA, "GET /insights/gaps": apiFailure() });
    renderWithQuery(<OverviewPage />);
    await findPanelState("overview-gaps", "error");
    await findPanelState("overview-top", "data");
    await findPanelState("overview-stats", "data");
  });
});
