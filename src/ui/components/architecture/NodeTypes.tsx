"use client";

import { Handle, type Node, type NodeProps } from "@xyflow/react";
import { createContext, useContext } from "react";
import { SIDES, SIDE_POSITION } from "@/components/architecture/build-flow";
import { StatusBadge } from "@/components/architecture/StatusBadge";
import type { Accent, ArchNodeData } from "@/content/architecture/types";
import { cn } from "@/lib/utils";

export type StatusMap = Record<string, string>;
export const StatusContext = createContext<StatusMap | null>(null);

type CardData = ArchNodeData & { isDimmed?: boolean };
type CardNode = Node<CardData>;

export const ACCENT_VAR: Record<Accent, string> = {
  ui: "var(--kind-ui)",
  api: "var(--kind-api)",
  services: "var(--kind-services)",
  agents: "var(--kind-agents)",
  data: "var(--kind-data)",
  ingestion: "var(--kind-ingestion)",
  external: "var(--kind-external)",
};

function Handles() {
  return (
    <>
      {SIDES.map((side) => (
        <span key={side}>
          <Handle
            id={`s-${side}`}
            type="source"
            position={SIDE_POSITION[side]}
            className="size-1! border-0! bg-transparent!"
          />
          <Handle
            id={`t-${side}`}
            type="target"
            position={SIDE_POSITION[side]}
            className="size-1! border-0! bg-transparent!"
          />
        </span>
      ))}
    </>
  );
}

function NodeStatus({ statusKey }: { statusKey: string | undefined }) {
  const statuses = useContext(StatusContext);
  if (!statusKey) return null;
  return <StatusBadge status={statuses?.[statusKey]} label={statuses?.[statusKey] ?? "unknown"} />;
}

interface ShellProps {
  data: CardData;
  selected: boolean;
  shape: string;
  children?: React.ReactNode;
}

function Shell({ data, selected, shape, children }: ShellProps) {
  return (
    <div
      data-testid="arch-node"
      data-node-kind={data.kind}
      style={{ opacity: data.isDimmed ? 0.35 : 1, borderLeftColor: ACCENT_VAR[data.accent] }}
      className={cn(
        "bg-surface1 relative h-full w-full overflow-hidden border border-l-4 px-3 py-2 transition-[opacity,border-color]",
        selected ? "border-line-strong ring-accent ring-2" : "border-line hover:border-line-strong",
        shape,
      )}
    >
      <Handles />
      {children}
    </div>
  );
}

function Title({ data }: { data: CardData }) {
  return (
    <div className="flex items-start justify-between gap-2">
      <div className="min-w-0">
        <p className="text-caption text-fg truncate font-semibold">{data.label}</p>
        {data.subtitle ? <p className="text-muted truncate text-xs">{data.subtitle}</p> : null}
      </div>
      <NodeStatus statusKey={data.statusKey} />
    </div>
  );
}

function BasicNode({
  data,
  selected,
  shape,
}: {
  data: CardData;
  selected: boolean;
  shape: string;
}) {
  return (
    <Shell data={data} selected={selected} shape={shape}>
      <Title data={data} />
      {data.componentId ? <p className="mono text-muted mt-1 text-xs">{data.componentId}</p> : null}
    </Shell>
  );
}

export function ComponentNode({ data, selected }: NodeProps<CardNode>) {
  return <BasicNode data={data} selected={selected} shape="rounded-card" />;
}

export function ActorNode({ data, selected }: NodeProps<CardNode>) {
  return <BasicNode data={data} selected={selected} shape="rounded-full pl-5" />;
}

export function ExternalNode({ data, selected }: NodeProps<CardNode>) {
  return <BasicNode data={data} selected={selected} shape="rounded-card border-dashed" />;
}

export function StoreNode({ data, selected }: NodeProps<CardNode>) {
  return <BasicNode data={data} selected={selected} shape="rounded-card rounded-t-[22px]" />;
}

export function JobNode({ data, selected }: NodeProps<CardNode>) {
  return <BasicNode data={data} selected={selected} shape="rounded-[6px]" />;
}

export function EntityNode({ data, selected }: NodeProps<CardNode>) {
  return (
    <Shell data={data} selected={selected} shape="rounded-card px-0 py-0">
      <p className="mono border-line bg-surface2 text-caption text-fg border-b px-3 py-1.5 font-semibold">
        {data.label}
      </p>
      <ul className="space-y-0 px-3 py-1.5">
        {data.columns?.map((column) => (
          <li key={column} className="mono text-muted h-[18px] truncate text-xs">
            {column}
          </li>
        ))}
      </ul>
    </Shell>
  );
}

export function GroupNode({ data }: NodeProps<Node<{ label: string; accent: Accent }>>) {
  return (
    <div className="rounded-card border-line-strong pointer-events-none h-full w-full border border-dashed">
      <span className="rounded-control border-line bg-surface1 text-muted absolute top-3 left-3 flex items-center gap-2 border px-2 py-0.5 text-xs font-medium">
        <span
          aria-hidden
          className="size-2 rounded-full"
          style={{ backgroundColor: ACCENT_VAR[data.accent] }}
        />
        {data.label}
      </span>
    </div>
  );
}

export const NODE_TYPES = {
  actor: ActorNode,
  external: ExternalNode,
  component: ComponentNode,
  store: StoreNode,
  job: JobNode,
  group: GroupNode,
  entity: EntityNode,
};
