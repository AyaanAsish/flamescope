import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ExplorerPage from "@/app/(dashboard)/explorer/page";
import { apiGet } from "@/lib/api/client";
import { BASS_II, FACETS, FLEX_2, pageOf } from "@/test-fixtures";
import {
  apiFailure,
  currentSearch,
  findPanelState,
  PENDING,
  renderWithQuery,
  serveAll,
  serveApi,
  setUrl,
  skeletonIn,
} from "@/test-utils";

vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/client")>()),
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

/** CF-04 list requests. */
const ROUTES = ["GET /investigations", "GET /facets"];
const DATA = { "GET /investigations": pageOf([BASS_II, FLEX_2]), "GET /facets": FACETS };

const grid = () => screen.getByRole("region", { name: "Investigations" });

describe("Explorer page /explorer (doc 10 section 5, CF-04)", () => {
  it("FR-01: shows card and filter skeletons while loading", async () => {
    serveApi(serveAll(ROUTES, PENDING));
    renderWithQuery(<ExplorerPage />);
    await findPanelState(grid, "loading");
    expect(skeletonIn(screen.getByTestId("explorer-filters"))).not.toBeNull();
  });

  it("FR-02: shows the empty state when no investigation matches", async () => {
    serveApi({ ...DATA, "GET /investigations": pageOf([]) });
    renderWithQuery(<ExplorerPage />);
    await findPanelState(grid, "empty");
  });

  it("FR-01: shows an error with retry for the list and the filters", async () => {
    serveApi(serveAll(ROUTES, apiFailure()));
    renderWithQuery(<ExplorerPage />);
    await findPanelState(grid, "error");
    await within(screen.getByTestId("explorer-filters")).findByRole("button", { name: "Retry" });
  });

  it("FR-01: data state renders investigation cards and the doc 10 control test IDs", async () => {
    serveApi(DATA);
    renderWithQuery(<ExplorerPage />);
    await findPanelState(grid, "data");
    expect(screen.getAllByTestId("investigation-card")).toHaveLength(2);
    expect(screen.getByTestId("explorer-filters")).toBeInTheDocument();
    expect(await screen.findByTestId("explorer-q")).toHaveAttribute("id", "explorer-q");
    expect(screen.getByTestId("explorer-sort")).toHaveAttribute("id", "explorer-sort");
  });

  it("FR-02: URL filters are sent to /investigations with oxygen converted from percent", async () => {
    setUrl("/explorer?fuel_phase=solid&o2_min=30&sort=habitat&q=flame");
    serveApi(DATA);
    renderWithQuery(<ExplorerPage />);
    await findPanelState(grid, "data");
    const params = vi.mocked(apiGet).mock.calls.find(([path]) => path === "/investigations")?.[1];
    expect(params).toMatchObject({
      fuel_phase: ["solid"],
      o2_min: 0.3,
      sort: "habitat",
      q: "flame",
    });
  });

  it("FR-02: changing the sort select mirrors it into the URL", async () => {
    serveApi(DATA);
    renderWithQuery(<ExplorerPage />);
    fireEvent.change(screen.getByTestId("explorer-sort"), { target: { value: "overall" } });
    await waitFor(() => expect(currentSearch().get("sort")).toBe("overall"));
  });
});
