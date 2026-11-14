import { screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import SafetyTechPage from "@/app/(dashboard)/safety-tech/page";
import { GAPS, SAFETY_TECH } from "@/test-fixtures";
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

/** CF-10 requests. */
const ROUTES = ["GET /insights/safety-tech", "GET /insights/gaps"];
const DATA = { "GET /insights/safety-tech": SAFETY_TECH, "GET /insights/gaps": GAPS };

function renderPage() {
  const { container } = renderWithQuery(<SafetyTechPage />);
  return () => container as HTMLElement;
}

describe("Safety Tech /safety-tech (doc 10 section 5, CF-10)", () => {
  it("FR-09: shows skeletons while loading", async () => {
    serveApi(serveAll(ROUTES, PENDING));
    await findPanelState(renderPage(), "loading");
  });

  it("FR-09: shows the empty state when no findings are curated", async () => {
    serveApi({ "GET /insights/safety-tech": { groups: [] }, "GET /insights/gaps": { gaps: [] } });
    await findPanelState(renderPage(), "empty");
    expect(screen.queryByTestId("safety-group")).not.toBeInTheDocument();
  });

  it("FR-09: shows errors with retry when the insights fail", async () => {
    serveApi(serveAll(ROUTES, apiFailure()));
    const page = await findPanelState(renderPage(), "error");
    expect(within(page).getAllByRole("button", { name: "Retry" })).toHaveLength(2);
  });

  it("FR-09: data state renders safety-group cards with findings, sources and gaps", async () => {
    serveApi(DATA);
    await findPanelState(renderPage(), "data");
    const group = await screen.findByTestId("safety-group");
    expect(group).toHaveAttribute("data-category", "detection");
    expect(
      within(group).getByText("Smoke particles are larger in microgravity."),
    ).toBeInTheDocument();
    expect(within(group).getByText("confidence 80 %")).toBeInTheDocument();
    expect(within(group).getByRole("link", { name: /BASS-II overview/ })).toBeInTheDocument();
    expect(screen.getByText("No partial-gravity data")).toBeInTheDocument();
    expect(screen.getByText("Expected: LUCI")).toBeInTheDocument();
  });
});
