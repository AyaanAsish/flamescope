"use client";

import { X } from "lucide-react";
import { useEffect } from "react";
import { StatusBadge } from "@/components/architecture/StatusBadge";
import { Badge } from "@/components/ui/badge";
import type { ArchNode } from "@/content/architecture/types";

interface NodePanelProps {
  node: ArchNode;
  status: string | undefined;
  onClose: () => void;
  onOpenFlow: (flowId: string) => void;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="text-muted mb-1.5 text-xs font-medium tracking-wide uppercase">{title}</h3>
      {children}
    </section>
  );
}

function MonoList({ items }: { items: string[] }) {
  return (
    <ul className="space-y-1">
      {items.map((item) => (
        <li key={item} className="mono text-muted text-xs break-all">
          {item}
        </li>
      ))}
    </ul>
  );
}

function FlowLinks({
  flows,
  onOpenFlow,
}: {
  flows: string[];
  onOpenFlow: (flowId: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {flows.map((flow) => (
        <button
          key={flow}
          type="button"
          onClick={() => onOpenFlow(flow)}
          className="mono rounded-control border-line bg-surface2 text-cool hover:border-cool border px-2 py-0.5 text-xs"
        >
          {flow}
        </button>
      ))}
    </div>
  );
}

function PanelBody({
  data,
  onOpenFlow,
}: {
  data: ArchNode["data"];
  onOpenFlow: (flowId: string) => void;
}) {
  const lists: [string, string[] | undefined][] = [
    ["Interfaces", data.interfaces],
    ["Columns", data.columns],
    ["Source files", data.files],
  ];
  return (
    <div className="flex-1 space-y-5 overflow-y-auto p-4">
      {data.responsibility ? (
        <Section title="Responsibility">
          <p className="text-muted text-sm">{data.responsibility}</p>
        </Section>
      ) : null}
      {lists.map(([title, items]) =>
        items?.length ? (
          <Section key={title} title={title}>
            <MonoList items={items} />
          </Section>
        ) : null,
      )}
      {data.flows?.length ? (
        <Section title="Related call flows">
          <FlowLinks flows={data.flows} onOpenFlow={onOpenFlow} />
        </Section>
      ) : null}
      {data.doc ? (
        <Section title="Document">
          <p className="mono text-muted text-xs">docs/architecture/{data.doc}</p>
        </Section>
      ) : null}
    </div>
  );
}

function useEscapeToClose(onClose: () => void) {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);
}

export function NodePanel({ node, status, onClose, onOpenFlow }: NodePanelProps) {
  const { data } = node;
  useEscapeToClose(onClose);
  return (
    <aside
      data-testid="arch-node-panel"
      aria-label={`${data.label} details`}
      className="slide-in border-line bg-surface1 absolute inset-y-0 right-0 z-10 flex w-96 max-w-full flex-col border-l"
    >
      <header className="border-line flex items-start justify-between gap-3 border-b p-4">
        <div className="min-w-0">
          <h2 className="text-base font-semibold">{data.label}</h2>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            {data.componentId ? (
              <Badge tone="accent" className="mono">
                {data.componentId}
              </Badge>
            ) : null}
            {data.kind ? <Badge>{data.kind}</Badge> : null}
            {data.statusKey ? <StatusBadge status={status} label={status ?? "unknown"} /> : null}
          </div>
        </div>
        <button
          type="button"
          aria-label="Close details"
          onClick={onClose}
          className="rounded-control text-muted hover:bg-surface2 hover:text-fg p-1.5"
        >
          <X className="size-4" aria-hidden />
        </button>
      </header>
      <PanelBody data={data} onOpenFlow={onOpenFlow} />
    </aside>
  );
}
