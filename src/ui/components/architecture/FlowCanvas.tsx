"use client";

import "@xyflow/react/dist/style.css";
import { Background, Controls, MiniMap, Panel, ReactFlow, type Node } from "@xyflow/react";
import { Download } from "lucide-react";
import { useMemo, useState } from "react";
import { buildEdges, buildNodes } from "@/components/architecture/build-flow";
import { Legend } from "@/components/architecture/Legend";
import { NODE_TYPES, ACCENT_VAR } from "@/components/architecture/NodeTypes";
import { NodePanel } from "@/components/architecture/NodePanel";
import type { ArchDiagram, ArchNode } from "@/content/architecture/types";

const MIN_ZOOM = 0.1;
const MAX_ZOOM = 1.5;
const FIT_PADDING = 0.15;
const GROUP_PREFIX = "group:";

interface FlowCanvasProps {
  diagram: ArchDiagram;
  statuses: Record<string, string>;
  onOpenFlow: (flowId: string) => void;
}

function minimapColor(node: Node): string {
  const accent = (node.data as { accent?: keyof typeof ACCENT_VAR } | undefined)?.accent;
  return accent ? ACCENT_VAR[accent] : "var(--border-strong)";
}

export function FlowCanvas({ diagram, statuses, onOpenFlow }: FlowCanvasProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const nodes = useMemo(
    () => buildNodes(diagram, hoveredId, selectedId),
    [diagram, hoveredId, selectedId],
  );
  const edges = useMemo(() => buildEdges(diagram, hoveredId), [diagram, hoveredId]);
  const selected: ArchNode | undefined = diagram.nodes.find((node) => node.id === selectedId);
  const toContentId = (node: Node) => (node.id.startsWith(GROUP_PREFIX) ? null : node.id);

  return (
    <div
      data-testid="arch-canvas"
      className="rounded-card border-line relative h-[calc(100vh-15rem)] min-h-[560px] overflow-hidden border"
    >
      <ReactFlow
        key={diagram.id}
        nodes={nodes}
        edges={edges}
        nodeTypes={NODE_TYPES}
        fitView
        fitViewOptions={{ padding: FIT_PADDING }}
        minZoom={MIN_ZOOM}
        maxZoom={MAX_ZOOM}
        nodesDraggable={false}
        nodesConnectable={false}
        proOptions={{ hideAttribution: true }}
        onNodeClick={(_, node) => setSelectedId(toContentId(node))}
        onNodeMouseEnter={(_, node) => setHoveredId(toContentId(node))}
        onNodeMouseLeave={() => setHoveredId(null)}
        onPaneClick={() => setSelectedId(null)}
      >
        <Background color="var(--border)" gap={24} />
        <Controls showInteractive={false} />
        <MiniMap pannable zoomable nodeColor={minimapColor} maskColor="var(--bg)" />
        <Panel position="top-left">
          <Legend />
        </Panel>
        <Panel position="top-right">
          <a
            href="/flamescope-architecture.drawio"
            download
            className="rounded-control border-line bg-surface1 text-caption text-fg hover:border-line-strong flex h-8 items-center gap-2 border px-3 font-medium transition-colors"
          >
            <Download className="size-3.5" aria-hidden /> Download draw.io
          </a>
        </Panel>
      </ReactFlow>
      {selected ? (
        <NodePanel
          node={selected}
          status={selected.data.statusKey ? statuses[selected.data.statusKey] : undefined}
          onClose={() => setSelectedId(null)}
          onOpenFlow={onOpenFlow}
        />
      ) : null}
    </div>
  );
}
