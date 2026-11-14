// @vitest-environment node
import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { DIAGRAMS, FLOW_FILES, FLOWS } from "@/content/architecture";
import type { ArchDiagram, ArchNode } from "@/content/architecture/types";

const UI_ROOT = path.resolve(__dirname, "..", "..");
const DOCS_DIR = path.resolve(UI_ROOT, "..", "..", "docs", "architecture");
const FLOWS_DIR = path.join(UI_ROOT, "content", "architecture", "flows");

/** Doc 10 section 6.2: minimum gap between node rectangles. */
const MIN_NODE_GAP_PX = 40;
/** Doc 10 section 6.1: five React Flow diagrams, the call flows and deployment. */
const TAB_DIAGRAMS = ["context", "layers", "components", "dataflow", "datamodel", "deployment"];
const SEVEN_TABS = TAB_DIAGRAMS.length + 1;
const NODE_TYPES = ["actor", "external", "component", "store", "job", "entity"];
const ACCENTS = ["ui", "api", "services", "agents", "data", "ingestion", "external"];
const SIDES = ["top", "right", "bottom", "left"];

function readDoc(name: string): string {
  return readFileSync(path.join(DOCS_DIR, name), "utf-8");
}

/** Every component ID written in doc 03 (for example C-UI, C-SVC). */
function componentIdsFromDoc03(): Set<string> {
  return new Set(readDoc("03-component-design.md").match(/\bC-[A-Z]+\b/g) ?? []);
}

/** `## CF-NN Title` headings of doc 09 mapped to their Mermaid block. */
function callFlowsFromDoc09(): Map<string, string> {
  const flows = new Map<string, string>();
  for (const section of readDoc("09-call-flows.md").split(/^## /m).slice(1)) {
    const id = /^(CF-\d{2})\b/.exec(section)?.[1];
    const mermaid = /```mermaid\n([\s\S]*?)```/.exec(section)?.[1];
    if (id) flows.set(id, mermaid ?? "");
  }
  return flows;
}

/** Horizontal and vertical clearance between two rectangles; negative on both axes means overlap. */
function clearance(a: ArchNode, b: ArchNode): { dx: number; dy: number } {
  const dx = Math.max(
    b.position.x - (a.position.x + a.width),
    a.position.x - (b.position.x + b.width),
  );
  const dy = Math.max(
    b.position.y - (a.position.y + a.height),
    a.position.y - (b.position.y + b.height),
  );
  return { dx, dy };
}

function nodePairs(diagram: ArchDiagram): [ArchNode, ArchNode][] {
  return diagram.nodes.flatMap((a, index) =>
    diagram.nodes.slice(index + 1).map((b) => [a, b] as [ArchNode, ArchNode]),
  );
}

function closePairs(diagram: ArchDiagram, minGap: number): string[] {
  return nodePairs(diagram)
    .filter(([a, b]) => {
      const { dx, dy } = clearance(a, b);
      return dx < minGap && dy < minGap;
    })
    .map(([a, b]) => `${a.id} / ${b.id}`);
}

const diagramCases = Object.entries(DIAGRAMS) as [string, ArchDiagram][];

describe("architecture content exports (doc 10 sections 6.1 and 6.5)", () => {
  it("FR-13: all seven tabs are exported: six diagrams plus the call flows", () => {
    expect(Object.keys(DIAGRAMS).sort()).toEqual([...TAB_DIAGRAMS].sort());
    expect(FLOWS.length).toBeGreaterThan(0);
    expect(Object.keys(DIAGRAMS).length + 1).toBe(SEVEN_TABS);
  });

  it("FR-13: each diagram id equals its tab key", () => {
    diagramCases.forEach(([key, diagram]) => expect(diagram.id).toBe(key));
  });
});

describe.each(diagramCases)("diagram %s (doc 10 section 6.2)", (_key, diagram) => {
  it("FR-13: node IDs are unique", () => {
    const ids = diagram.nodes.map((node) => node.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("FR-13: every edge references existing nodes and edge IDs are unique", () => {
    const ids = new Set(diagram.nodes.map((node) => node.id));
    const dangling = diagram.edges.filter((edge) => !ids.has(edge.source) || !ids.has(edge.target));
    expect(dangling.map((edge) => edge.id)).toEqual([]);
    expect(new Set(diagram.edges.map((edge) => edge.id)).size).toBe(diagram.edges.length);
  });

  it("FR-13: no two node rectangles overlap (declared width and height)", () => {
    expect(closePairs(diagram, 0)).toEqual([]);
  });

  it("FR-13: nodes keep the minimum 40 px gap", () => {
    expect(closePairs(diagram, MIN_NODE_GAP_PX)).toEqual([]);
  });

  it("FR-13: every componentId is a component ID of doc 03", () => {
    const known = componentIdsFromDoc03();
    const unknown = diagram.nodes
      .map((node) => node.data.componentId)
      .filter((id) => id && !known.has(id));
    expect(unknown).toEqual([]);
  });

  it("FR-13: node types, accents, sizes, edge sides and groups use the documented values", () => {
    const groups = new Set(diagram.groups.map((group) => group.id));
    diagram.nodes.forEach((node) => {
      expect(NODE_TYPES).toContain(node.type);
      expect(ACCENTS).toContain(node.data.accent);
      expect(node.width > 0 && node.height > 0).toBe(true);
      expect(node.group === undefined || groups.has(node.group)).toBe(true);
    });
    const sides = diagram.edges
      .flatMap((edge) => [edge.sourceSide, edge.targetSide])
      .filter(Boolean);
    sides.forEach((side) => expect(SIDES).toContain(side));
    expect(["LR", "TB"]).toContain(diagram.direction);
  });
});

describe("components diagram (doc 10 section 6.2)", () => {
  it("FR-13: one node per doc 03 component ID, node id equal to componentId", () => {
    const nodes = DIAGRAMS.components.nodes.filter((node) => node.data.componentId);
    nodes.forEach((node) => expect(node.id).toBe(node.data.componentId));
    expect(new Set(nodes.map((node) => node.id))).toEqual(componentIdsFromDoc03());
  });
});

describe("call flows (doc 09, doc 10 sections 6.1 and 6.5)", () => {
  it("FR-13: FLOWS lists exactly the CF headings of doc 09, in order", () => {
    expect(FLOWS.map((flow) => flow.id)).toEqual([...callFlowsFromDoc09().keys()]);
  });

  it("FR-13: a flows/cf-NN.mmd file exists for every CF of doc 09 and nothing else", () => {
    const expected = [...callFlowsFromDoc09().keys()].map((id) => `${id.toLowerCase()}.mmd`);
    expect(FLOW_FILES).toEqual(expected);
    expected.forEach((file) => expect(existsSync(path.join(FLOWS_DIR, file))).toBe(true));
    expect(readdirSync(FLOWS_DIR).sort()).toEqual([...expected].sort());
  });

  it("FR-13: each .mmd file is a verbatim copy of the Mermaid block of its doc 09 section", () => {
    for (const [id, mermaid] of callFlowsFromDoc09()) {
      const source = readFileSync(path.join(FLOWS_DIR, `${id.toLowerCase()}.mmd`), "utf-8");
      expect(source.trim(), id).toBe(mermaid.trim());
    }
  });
});
