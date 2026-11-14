"use client";

import "@xyflow/react/dist/style.css";
import { Background, Position, ReactFlow, type Edge, type Node } from "@xyflow/react";
import { useMemo } from "react";
import { Card, CardHeader } from "@/components/ui/card";
import { DataPanel } from "@/components/ui/panel-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useHardware } from "@/lib/api/hooks";
import type { LineageEdge, LineageGraph as LineageData, LineageNode } from "@/lib/api/types";

const COLUMN_X = { project: 0, investigation: 280, hardware: 560, parent: 840 } as const;
const ROW_HEIGHT = 96;
const NODE_WIDTH = 190;

type Column = keyof typeof COLUMN_X;

const TYPE_BORDER: Record<LineageNode["type"], string> = {
  investigation: "var(--accent)",
  hardware: "var(--cool)",
  project: "var(--liquid)",
};

function neighbourhood(
  graph: LineageData,
  acronyms: string[],
): { nodes: LineageNode[]; edges: LineageEdge[] } {
  const keep = new Set(acronyms.map((acronym) => `inv:${acronym}`));
  const direct = graph.edges.filter((edge) => keep.has(edge.source) || keep.has(edge.target));
  direct.forEach((edge) => [edge.source, edge.target].forEach((id) => keep.add(id)));
  const chain = graph.edges.filter((edge) => edge.role === "hosted_in" && keep.has(edge.source));
  chain.forEach((edge) => keep.add(edge.target));
  return {
    nodes: graph.nodes.filter((node) => keep.has(node.id)),
    edges: graph.edges.filter((edge) => keep.has(edge.source) && keep.has(edge.target)),
  };
}

function columnOf(node: LineageNode, parents: Set<string>): Column {
  if (node.type === "hardware" && parents.has(node.id)) return "parent";
  return node.type;
}

function layout(nodes: LineageNode[], edges: LineageEdge[]): Node[] {
  const parents = new Set(
    edges.filter((edge) => edge.role === "hosted_in").map((edge) => edge.target),
  );
  const rows: Record<Column, number> = { project: 0, investigation: 0, hardware: 0, parent: 0 };
  return nodes.map((node) => {
    const column = columnOf(node, parents);
    const y = rows[column]++ * ROW_HEIGHT;
    return {
      id: node.id,
      position: { x: COLUMN_X[column], y },
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
      draggable: false,
      data: {
        label: (
          <div className="text-left">
            <p className="text-sm font-semibold">{node.label}</p>
            <p className="text-muted text-xs">
              {node.type === "hardware" && node.kind ? `hardware, ${node.kind}` : node.type}
            </p>
          </div>
        ),
      },
      style: {
        width: NODE_WIDTH,
        background: "var(--surface-1)",
        color: "var(--text)",
        border: `1px solid ${TYPE_BORDER[node.type]}`,
        borderRadius: 10,
        padding: 8,
      },
    };
  });
}

function toEdges(edges: LineageEdge[]): Edge[] {
  return edges.map((edge, index) => ({
    id: `${edge.source}-${edge.target}-${index}`,
    source: edge.source,
    target: edge.target,
    label: edge.role.replaceAll("_", " "),
    type: "smoothstep",
    labelStyle: { fill: "var(--text-muted)", fontSize: 11 },
    labelBgStyle: { fill: "var(--bg)" },
    style: { stroke: "var(--edge)", strokeWidth: 1.5 },
  }));
}

function Lineage({ graph, acronyms }: { graph: LineageData; acronyms: string[] }) {
  const { nodes, edges } = useMemo(() => {
    const sub = neighbourhood(graph, acronyms);
    return { nodes: layout(sub.nodes, sub.edges), edges: toEdges(sub.edges) };
  }, [graph, acronyms]);
  return (
    <div className="rounded-control border-line h-96 border">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        nodesDraggable={false}
        nodesConnectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="var(--border)" gap={24} />
      </ReactFlow>
    </div>
  );
}

export function LineageGraph({ acronyms }: { acronyms: string[] }) {
  const hardware = useHardware();
  return (
    <Card data-testid="lineage-graph">
      <CardHeader
        title="Hardware lineage"
        description="Facilities, apparatus and projects shared by the selected investigations."
      />
      <DataPanel
        query={hardware}
        isEmpty={(graph) => graph.nodes.length === 0}
        emptyMessage="No hardware lineage is recorded."
        skeleton={<Skeleton className="h-96" />}
      >
        {(graph) => <Lineage graph={graph} acronyms={acronyms} />}
      </DataPanel>
    </Card>
  );
}
