import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ScenarioPage from "@/app/(dashboard)/scenario/page";
import { apiPost } from "@/lib/api/client";
import { SCORE_DISCLAIMER } from "@/lib/constants";
import { PRESETS, SCENARIO } from "@/test-fixtures";
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

const DATA = { "GET /meta/presets": PRESETS, "POST /scenario": SCENARIO };
const LUNAR = "/scenario?preset=lunar_habitat";

function renderPage() {
  const { container } = renderWithQuery(<ScenarioPage />);
  return () => container as HTMLElement;
}

describe("Scenario Lab /scenario (doc 10 section 5, CF-07)", () => {
  it("FR-07: shows a skeleton while matching, with the form and disclaimer visible", async () => {
    setUrl(LUNAR);
    serveApi({ "GET /meta/presets": PRESETS, "POST /scenario": PENDING });
    await findPanelState(renderPage(), "loading");
    expect(screen.getByTestId("scenario-form")).toBeInTheDocument();
    expect(screen.getByText(new RegExp(SCORE_DISCLAIMER))).toBeInTheDocument();
  });

  it("FR-07: with no preset and no value the page asks for input and sends no request", async () => {
    serveApi(DATA);
    renderPage();
    expect(await screen.findByText(/Choose a preset or set a value/)).toBeInTheDocument();
    expect(vi.mocked(apiPost)).not.toHaveBeenCalled();
  });

  it("FR-07: an empty match list says so while coverage and bounding still render", async () => {
    setUrl(LUNAR);
    serveApi({ ...DATA, "POST /scenario": { ...SCENARIO, matches: [] } });
    renderPage();
    expect(
      await screen.findByText("No investigation has runs near this scenario."),
    ).toBeInTheDocument();
    expect(screen.getByTestId("coverage-panel")).toBeInTheDocument();
    expect(screen.getByTestId("gravity-bounding")).toBeInTheDocument();
  });

  it("FR-07: a failed match shows an error with retry", async () => {
    setUrl(LUNAR);
    serveApi({ ...DATA, "POST /scenario": apiFailure(400, "Unknown preset") });
    const panel = await findPanelState(renderPage(), "error");
    expect(within(panel).getByText("Unknown preset")).toBeInTheDocument();
  });

  it("FR-16: data state exposes the doc 10 test IDs and labels the assumed default", async () => {
    setUrl(LUNAR);
    serveApi(DATA);
    renderPage();
    expect(await screen.findByTestId("scenario-match")).toHaveAttribute("data-acronym", "BASS-II");
    ["scenario-form", "coverage-panel", "gravity-bounding"].forEach((id) =>
      expect(screen.getByTestId(id)).toBeInTheDocument(),
    );
    ["scenario-preset", "scenario-phase", "scenario-material"].forEach((id) =>
      expect(screen.getByTestId(id)).toHaveAttribute("id", id),
    );
    expect(await screen.findByText("assumed default")).toBeInTheDocument();
    expect(
      within(screen.getByTestId("gravity-bounding")).getByText("No partial-gravity data"),
    ).toBeInTheDocument();
  });

  it("FR-07: the lunar preset is sent as the preset with explain false first", async () => {
    setUrl(LUNAR);
    serveApi(DATA);
    renderPage();
    await screen.findByTestId("scenario-match");
    expect(vi.mocked(apiPost)).toHaveBeenCalledWith("/scenario", {
      explain: false,
      preset: "lunar_habitat",
    });
  });

  it("FR-07: Explain requests the interpretation with explain true", async () => {
    setUrl(LUNAR);
    serveApi(DATA);
    renderPage();
    await screen.findByTestId("scenario-match");
    fireEvent.click(screen.getByRole("button", { name: /explain/i }));
    await waitFor(() =>
      expect(vi.mocked(apiPost)).toHaveBeenCalledWith("/scenario", {
        explain: true,
        preset: "lunar_habitat",
      }),
    );
  });

  it("FR-07: choosing a phase mirrors it into the URL", async () => {
    setUrl(LUNAR);
    serveApi(DATA);
    renderPage();
    fireEvent.change(await screen.findByTestId("scenario-phase"), { target: { value: "solid" } });
    await waitFor(() => expect(currentSearch().get("phase")).toBe("solid"));
  });
});
