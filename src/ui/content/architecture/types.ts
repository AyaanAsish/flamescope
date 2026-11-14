export type NodeType = "actor" | "external" | "component" | "store" | "job" | "entity";
export type Accent = "ui" | "api" | "services" | "agents" | "data" | "ingestion" | "external";
export type Side = "top" | "right" | "bottom" | "left";
export type Direction = "LR" | "TB";

export type ArchNodeData = {
  label: string;
  accent: Accent;
  subtitle?: string;
  componentId?: string;
  kind?: string;
  responsibility?: string;
  interfaces?: string[];
  files?: string[];
  flows?: string[];
  statusKey?: string;
  doc?: string;
  columns?: string[];
};

export interface ArchNode {
  id: string;
  type: NodeType;
  group?: string;
  position: { x: number; y: number };
  width: number;
  height: number;
  data: ArchNodeData;
}

export interface ArchGroup {
  id: string;
  label: string;
  color: Accent;
}

export interface ArchEdge {
  id: string;
  source: string;
  target: string;
  label: string;
  animated: boolean;
  llm?: boolean;
  sourceSide?: Side;
  targetSide?: Side;
}

export interface ArchDiagram {
  id: string;
  title: string;
  direction: Direction;
  nodes: ArchNode[];
  groups: ArchGroup[];
  edges: ArchEdge[];
}

export type LlmUsage = "none" | "optional" | "yes";

export interface FlowMeta {
  id: string;
  title: string;
  llm: LlmUsage;
  endpoints: string[];
  failure: string;
  doc: string;
}
