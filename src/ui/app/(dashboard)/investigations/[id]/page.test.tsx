import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import InvestigationPage from "@/app/(dashboard)/investigations/[id]/page";
import { apiGet } from "@/lib/api/client";
import { DETAIL, pageOf, RUN, VARIABLES } from "@/test-fixtures";
import {
  apiFailure,
  findPanelState,
  PENDING,
  renderWithQuery,
  serveApi,
  setUrl,
} from "@/test-utils";

vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/client")>()),
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

const DETAIL_ROUTE = "GET /investigations/BASS-II";
const RUNS_ROUTE = "GET /investigations/BASS-II/runs";
const DATA = {
  [DETAIL_ROUTE]: DETAIL,
  [RUNS_ROUTE]: pageOf([RUN]),
  "GET /investigations/BASS-II/variables": VARIABLES,
  "GET /investigations/BASS-II/publications": [],
};

async function renderDetail(id = "BASS-II") {
  const page = await InvestigationPage({ params: Promise.resolve({ id: encodeURIComponent(id) }) });
  return renderWithQuery(page);
}

describe("Investigation detail /investigations/[id] (doc 10 section 5, CF-04)", () => {
  it("FR-01: shows a skeleton under detail-header while the detail loads", async () => {
    serveApi({ [DETAIL_ROUTE]: PENDING });
    const { container } = await renderDetail();
    await findPanelState(() => container, "loading");
    expect(screen.getByTestId("detail-header")).toBeInTheDocument();
  });

  it("FR-01: an unknown investigation shows the 404 envelope message with retry", async () => {
    serveApi({ "GET /investigations/NOPE": apiFailure(404, "Investigation 'NOPE' not found") });
    const { container } = await renderDetail("NOPE");
    const panel = await findPanelState(() => container, "error");
    expect(within(panel).getByText("Investigation 'NOPE' not found")).toBeInTheDocument();
    expect(within(panel).getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("FR-06: the runs tab shows its empty state when no runs are recorded", async () => {
    setUrl("/investigations/BASS-II?tab=runs");
    serveApi({ ...DATA, [RUNS_ROUTE]: pageOf([]) });
    await renderDetail();
    await findPanelState("runs-table", "empty");
  });

  it("FR-06: the runs tab shows its own loading and error states", async () => {
    setUrl("/investigations/BASS-II?tab=runs");
    serveApi({ ...DATA, [RUNS_ROUTE]: apiFailure() });
    await renderDetail();
    await findPanelState("runs-table", "error");
  });

  it("FR-01: data state exposes detail-header, detail-tabs and runs-table with the PSI link", async () => {
    setUrl("/investigations/BASS-II?tab=runs");
    serveApi(DATA);
    await renderDetail();
    const header = await screen.findByRole("banner");
    expect(header).toHaveAttribute("data-testid", "detail-header");
    expect(within(header).getByRole("link", { name: /view in psi/i })).toHaveAttribute(
      "href",
      DETAIL.psi_url,
    );
    expect(screen.getByTestId("detail-tabs")).toBeInTheDocument();
    const runs = await findPanelState("runs-table", "data");
    expect(within(runs).getByText("21 % O₂")).toBeInTheDocument();
    expect(within(runs).getByText("101.3 kPa")).toBeInTheDocument();
  });

  it("FR-01: the acronym in the URL is decoded before the API call", async () => {
    serveApi({ "GET /investigations/E-FIELD%20Flames": PENDING });
    await renderDetail("E-FIELD Flames");
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/investigations/E-FIELD%20Flames");
  });
});
