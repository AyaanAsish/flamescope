"use client";

import { SequenceDiagram } from "@/components/architecture/SequenceDiagram";
import { Badge } from "@/components/ui/badge";
import { FLOWS, type FlowMeta } from "@/content/architecture";
import { cn } from "@/lib/utils";

const LLM_LABEL: Record<FlowMeta["llm"], string> = {
  none: "LLM: none",
  optional: "LLM: optional",
  yes: "LLM: yes",
};
const LLM_TONE = { none: "neutral", optional: "warning", yes: "accent" } as const;

interface FlowViewerProps {
  activeId: string;
  sources: Record<string, string>;
  onSelect: (flowId: string) => void;
}

export function FlowViewer({ activeId, sources, onSelect }: FlowViewerProps) {
  const active = FLOWS.find((flow) => flow.id === activeId) ?? FLOWS[0];
  if (!active) return null;
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
      <ul aria-label="Call flows" className="space-y-1.5 self-start">
        {FLOWS.map((flow) => (
          <li key={flow.id}>
            <button
              type="button"
              aria-current={flow.id === active.id}
              onClick={() => onSelect(flow.id)}
              className={cn(
                "rounded-card w-full border p-3 text-left transition-colors",
                flow.id === active.id
                  ? "border-line-strong bg-surface2"
                  : "border-line bg-surface1 hover:border-line-strong",
              )}
            >
              <span className="flex items-center justify-between gap-2">
                <span className="mono text-muted text-xs">{flow.id}</span>
                <Badge tone={LLM_TONE[flow.llm]}>{LLM_LABEL[flow.llm]}</Badge>
              </span>
              <span className="mt-1 block text-sm font-medium">{flow.title}</span>
            </button>
          </li>
        ))}
      </ul>
      <div className="min-w-0 space-y-4">
        <div>
          <h2 className="text-base font-semibold">
            {active.id} {active.title}
          </h2>
          {active.endpoints.length ? (
            <p className="mono text-muted mt-1 text-xs">{active.endpoints.join("  |  ")}</p>
          ) : null}
        </div>
        <SequenceDiagram flowId={active.id} source={sources[active.id] ?? ""} />
        <div className="rounded-card border-line bg-surface1 border p-4">
          <p className="text-muted mb-1 text-xs font-medium tracking-wide uppercase">
            Failure behaviour
          </p>
          <p className="text-muted text-sm">{active.failure}</p>
          <p className="mono text-muted mt-2 text-xs">docs/architecture/{active.doc}</p>
        </div>
      </div>
    </div>
  );
}
