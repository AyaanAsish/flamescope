import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import EarthPage from "@/app/(dashboard)/earth/page";
import { apiGet } from "@/lib/api/client";
import { EARTH } from "@/test-fixtures";
import {
  apiFailure,
  currentSearch,
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

const ROUTE = "GET /earth-applications";

function renderPage() {
  const { container } = renderWithQuery(<EarthPage />);
  return () => container as HTMLElement;
}

describe("Earth Apps /earth (doc 10 section 5, CF-10)", () => {
  it("FR-10: shows a skeleton while loading", async () => {
    serveApi({ [ROUTE]: PENDING });
    await findPanelState(renderPage(), "loading");
  });

  it("FR-10: shows the empty state when a sector has no applications", async () => {
    serveApi({ [ROUTE]: { items: [] } });
    await findPanelState(renderPage(), "empty");
  });

  it("FR-10: shows an error with retry", async () => {
    serveApi({ [ROUTE]: apiFailure() });
    const page = await findPanelState(renderPage(), "error");
    expect(within(page).getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("FR-10: data state renders earth-card items with linked investigations and references", async () => {
    serveApi({ [ROUTE]: EARTH });
    renderPage();
    const card = await screen.findByTestId("earth-card");
    expect(within(card).getByText("Fine water mist extinguishers")).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: "FLEX-2" })).toHaveAttribute(
      "href",
      "/investigations/FLEX-2",
    );
    expect(within(card).getByRole("link", { name: /BASS-II overview/ })).toBeInTheDocument();
  });

  it("FR-10: the sector filter is mirrored in the URL and sent to the API", async () => {
    setUrl("/earth?sector=firefighting");
    serveApi({ [ROUTE]: EARTH });
    renderPage();
    await screen.findByTestId("earth-card");
    expect(vi.mocked(apiGet)).toHaveBeenCalledWith("/earth-applications", {
      sector: "firefighting",
    });
    fireEvent.click(screen.getByRole("button", { name: "Wildfire" }));
    await waitFor(() => expect(currentSearch().get("sector")).toBe("wildfire"));
  });
});
