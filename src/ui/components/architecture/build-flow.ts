import { MarkerType, Position, type Edge, type Node } from "@xyflow/react";
import type {
  ArchDiagram,
  ArchEdge,
  ArchGroup,
  ArchNode,
  Side,
} from "@/content/architecture/types";

export const GROUP_PADDING = { left: 24, right: 24, top: 44, bottom: 24 } as const;
export const DIMMED_OPACITY = 0.35;

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

const SIDE_POSITION: Record<Side, Position> = {
  top: Position.Top,
  right: Position.Right,
  bottom: Position.Bottom,
  left: Position.Left,
};

export function nodeRect(node: ArchNode): Rect {
  return { x: node.position.x, y: node.position.y, width: node.width, height: node.height };
}

export function groupRect(diagram: ArchDiagram, groupId: string): Rect | null {
  const members = diagram.nodes.filter((node) => node.group === groupId).map(nodeRect);
  if (members.length === 0) return null;
  const left = Math.min(...members.map((rect) => rect.x)) - GROUP_PADDING.left;
  const top = Math.min(...members.map((rect) => rect.y)) - GROUP_PADDING.top;
  const right = Math.max(...members.map((rect) => rect.x + rect.width)) + GROUP_PADDING.right;
  const bottom = Math.max(...members.map((rect) => rect.y + rect.height)) + GROUP_PADDING.bottom;
  return { x: left, y: top, width: right - left, height: bottom - top };
}

export function connectedIds(diagram: ArchDiagram, nodeId: string): Set<string> {
  const ids = new Set([nodeId]);
  for (const edge of diagram.edges) {
    if (edge.source === nodeId) ids.add(edge.target);
    if (edge.target === nodeId) ids.add(edge.source);
  }
  return ids;
}

export function defaultSides(direction: ArchDiagram["direction"]): [Side, Side] {
  return direction === "LR" ? ["right", "left"] : ["bottom", "top"];
}

function groupNode(diagram: ArchDiagram, group: ArchGroup): Node | null {
  const rect = groupRect(diagram, group.id);
  if (!rect) return null;
  return {
    id: `group:${group.id}`,
    type: "group",
    position: { x: rect.x, y: rect.y },
    data: { label: group.label, accent: group.color },
    style: { width: rect.width, height: rect.height },
    zIndex: -1,
    draggable: false,
    selectable: false,
    focusable: false,
  };
}

function contentNode(
  diagram: ArchDiagram,
  node: ArchNode,
  hoveredId: string | null,
  selectedId: string | null,
): Node {
  const [, targetSide] = defaultSides(diagram.direction);
  const isDimmed = hoveredId !== null && !connectedIds(diagram, hoveredId).has(node.id);
  return {
    id: node.id,
    type: node.type,
    position: node.position,
    width: node.width,
    height: node.height,
    data: { ...node.data, isDimmed, targetSide },
    draggable: false,
    selected: node.id === selectedId,
  };
}

export function buildNodes(
  diagram: ArchDiagram,
  hoveredId: string | null,
  selectedId: string | null,
): Node[] {
  const groups = diagram.groups
    .map((group) => groupNode(diagram, group))
    .filter((node): node is Node => node !== null);
  return [
    ...groups,
    ...diagram.nodes.map((node) => contentNode(diagram, node, hoveredId, selectedId)),
  ];
}

function edgeOpacity(edge: ArchEdge, hoveredId: string | null): number {
  if (hoveredId === null) return 1;
  return edge.source === hoveredId || edge.target === hoveredId ? 1 : DIMMED_OPACITY;
}

export function buildEdges(diagram: ArchDiagram, hoveredId: string | null): Edge[] {
  const [defaultSource, defaultTarget] = defaultSides(diagram.direction);
  return diagram.edges.map((edge) => {
    const color = edge.llm ? "var(--edge-llm)" : "var(--edge)";
    return {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      sourceHandle: `s-${edge.sourceSide ?? defaultSource}`,
      targetHandle: `t-${edge.targetSide ?? defaultTarget}`,
      type: "smoothstep",
      label: edge.label || undefined,
      animated: edge.animated,
      markerEnd: { type: MarkerType.ArrowClosed, color },
      labelStyle: { fill: "var(--text-muted)", fontSize: 11 },
      labelBgStyle: { fill: "var(--bg)" },
      labelBgPadding: [6, 3],
      labelBgBorderRadius: 4,
      style: {
        stroke: color,
        strokeWidth: 1.5,
        strokeDasharray: edge.llm ? "6 4" : undefined,
        opacity: edgeOpacity(edge, hoveredId),
      },
    };
  });
}

export const SIDES: readonly Side[] = ["top", "right", "bottom", "left"];
export { SIDE_POSITION };
