import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ExtractPage from "@/app/(dashboard)/extract/page";
import { apiDownload, apiPost, saveFile } from "@/lib/api/client";
import { BASS_II, DICTIONARY, pageOf, PREVIEW_TABLE } from "@/test-fixtures";
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
  apiDownload: vi.fn(async () => ({ blob: new Blob(["investigation\n"]), filename: "runs.csv" })),
  saveFile: vi.fn(),
}));

/** CF-08 requests plus the investigation checklist. */
const ROUTES = ["GET /extract/dictionary", "POST /extract/preview", "GET /investigations"];
const DATA = {
  "GET /extract/dictionary": DICTIONARY,
  "POST /extract/preview": PREVIEW_TABLE,
  "GET /investigations": pageOf([BASS_II]),
};

describe("Data Extract /extract (doc 10 section 5, CF-08)", () => {
  it("FR-08: shows the preview skeleton while loading", async () => {
    serveApi(serveAll(ROUTES, PENDING));
    renderWithQuery(<ExtractPage />);
    await findPanelState("extract-preview", "loading");
    expect(screen.getByTestId("extract-query")).toBeInTheDocument();
  });

  it("FR-08: shows the empty state when no run matches", async () => {
    serveApi({ ...DATA, "POST /extract/preview": { ...PREVIEW_TABLE, rows: [], total: 0 } });
    renderWithQuery(<ExtractPage />);
    await findPanelState("extract-preview", "empty");
  });

  it("FR-08: shows an error with retry when the preview fails", async () => {
    serveApi({ ...DATA, "POST /extract/preview": apiFailure(400, "Unknown column 'foo'") });
    renderWithQuery(<ExtractPage />);
    const panel = await findPanelState("extract-preview", "error");
    expect(within(panel).getByText("Unknown column 'foo'")).toBeInTheDocument();
  });

  it("FR-08: data state exposes query, preview and export buttons with oxygen in percent", async () => {
    serveApi(DATA);
    renderWithQuery(<ExtractPage />);
    const preview = await findPanelState("extract-preview", "data");
    expect(within(preview).getByText("Oxygen fraction (%)")).toBeInTheDocument();
    expect(within(preview).getByText("21")).toBeInTheDocument();
    expect(within(preview).getByText("Pressure (kPa)")).toBeInTheDocument();
    ["extract-query", "export-csv", "export-json"].forEach((id) =>
      expect(screen.getByTestId(id)).toBeInTheDocument(),
    );
  });

  it("FR-08: URL filters become the preview request with oxygen as a fraction", async () => {
    setUrl("/extract?phase=solid&o2_min=30&cols=investigation,o2_fraction");
    serveApi(DATA);
    renderWithQuery(<ExtractPage />);
    await findPanelState("extract-preview", "data");
    const body = vi.mocked(apiPost).mock.calls.find(([path]) => path === "/extract/preview")?.[1];
    expect(body).toMatchObject({
      filters: { fuel_phase: ["solid"], o2_min: 0.3 },
      columns: ["investigation", "o2_fraction"],
      limit: 50,
    });
  });

  it.each([
    ["export-csv", "csv"],
    ["export-json", "json"],
  ])("FR-08: %s downloads /extract/export with format %s", async (testId, format) => {
    serveApi(DATA);
    renderWithQuery(<ExtractPage />);
    fireEvent.click(screen.getByTestId(testId));
    await waitFor(() => expect(vi.mocked(saveFile)).toHaveBeenCalled());
    expect(vi.mocked(apiDownload)).toHaveBeenCalledWith(
      "/extract/export",
      expect.objectContaining({ format }),
    );
  });
});
