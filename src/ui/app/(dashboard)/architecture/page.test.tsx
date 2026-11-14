import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ArchitecturePage from "@/app/(dashboard)/architecture/page";
import { DIAGRAMS } from "@/content/architecture";
import { STATUS } from "@/test-fixtures";
import { apiFailure, PENDING, renderWithQuery, serveApi, setUrl } from "@/test-utils";

vi.mock("@/lib/api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api/client")>()),
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

/** Mermaid needs a real layout engine; the stub returns a fixed SVG for the flow it was given. */
vi.mock("mermaid", () => ({
  default: {
    initialize: vi.fn(),
    render: vi.fn(async (id: string) => ({ svg: `<svg data-render-id="${id}"></svg>` })),
  },
}));

/** Doc 10 section 6.1 tab labels, in order. */
const TAB_LABELS = [
  "System context",
  "Layers",
  "Components",
  "Data flow",
  "Data model",
  "Call flows",
  "Deployment",
];
const ROUTE = "GET /meta/status";

function badgeStatuses(): string[] {
  const nodes = screen.getAllByTestId("arch-node");
  return nodes.flatMap((node) =>
    Array.from(node.querySelectorAll("[data-status]")).map(
      (badge) => badge.getAttribute("data-status") ?? "",
    ),
  );
}

async function renderComponentsTab() {
  setUrl("/architecture?tab=components");
  renderWithQuery(<ArchitecturePage />);
  return screen.findAllByTestId("arch-node");
}

describe("Architecture page /architecture (doc 10 sections 5 and 6, CF-12)", () => {
  it("FR-13: the seven documented tabs are rendered under arch-tabs", () => {
    serveApi({ [ROUTE]: STATUS });
    renderWithQuery(<ArchitecturePage />);
    const tabs = within(screen.getByTestId("arch-tabs")).getAllByRole("tab");
    expect(tabs.map((tab) => tab.textContent)).toEqual(TAB_LABELS);
  });

  it("FR-13: while /meta/status loads the diagram renders and badges read unknown", async () => {
    serveApi({ [ROUTE]: PENDING });
    const nodes = await renderComponentsTab();
    expect(screen.getByTestId("arch-canvas")).toBeInTheDocument();
    expect(nodes).toHaveLength(DIAGRAMS.components.nodes.length);
    expect(new Set(badgeStatuses())).toEqual(new Set(["unknown"]));
  });

  it("FR-13: an empty status list leaves every badge unknown", async () => {
    serveApi({ [ROUTE]: { components: [] } });
    await renderComponentsTab();
    await waitFor(() => expect(new Set(badgeStatuses())).toEqual(new Set(["unknown"])));
  });

  it("FR-13: a failed /meta/status still renders the static diagrams (CF-12 failure note)", async () => {
    serveApi({ [ROUTE]: apiFailure() });
    const nodes = await renderComponentsTab();
    expect(nodes.length).toBeGreaterThan(0);
    expect(badgeStatuses()).not.toContain("up");
  });

  it("FR-13: data state shows live badges and a node opens arch-node-panel", async () => {
    serveApi({ [ROUTE]: STATUS });
    await renderComponentsTab();
    await waitFor(() => expect(badgeStatuses()).toContain("up"));
    expect(badgeStatuses()).toContain("mock");
    const apiNode = screen
      .getAllByTestId("arch-node")
      .find((node) => node.textContent?.includes("C-API"));
    fireEvent.click(apiNode!);
    const panel = await screen.findByTestId("arch-node-panel");
    expect(within(panel).getByText("Source files")).toBeInTheDocument();
    expect(within(panel).getByText("Related call flows")).toBeInTheDocument();
  });

  it("FR-13: the call-flows tab renders arch-sequence for the selected flow", async () => {
    setUrl("/architecture?tab=flows&cf=CF-07");
    serveApi({ [ROUTE]: STATUS });
    renderWithQuery(<ArchitecturePage />);
    const sequence = await screen.findByTestId("arch-sequence");
    expect(sequence).toHaveAttribute("data-flow", "CF-07");
    await waitFor(() => expect(sequence.querySelector("svg")).not.toBeNull());
    expect(screen.getAllByRole("button", { name: /CF-\d{2}/ })).toHaveLength(13);
  });

  it("FR-13: the draw.io download links to the public file", async () => {
    serveApi({ [ROUTE]: STATUS });
    renderWithQuery(<ArchitecturePage />);
    const link = await screen.findByRole("link", { name: /download draw\.io/i });
    expect(link).toHaveAttribute("href", "/flamescope-architecture.drawio");
  });
});
