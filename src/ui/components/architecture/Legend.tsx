import { ACCENT_VAR } from "@/components/architecture/NodeTypes";
import type { Accent } from "@/content/architecture/types";

const ACCENT_LABELS: [Accent, string][] = [
  ["ui", "UI"],
  ["api", "API"],
  ["services", "Services"],
  ["agents", "Agents"],
  ["data", "Data"],
  ["ingestion", "Ingestion"],
  ["external", "External"],
];

const STATUS_LEGEND: [string, string][] = [
  ["bg-success", "up"],
  ["bg-warning", "mock or idle"],
  ["bg-danger", "down"],
];

export function Legend() {
  return (
    <div className="rounded-card border-line bg-surface1 text-muted w-44 space-y-2.5 border p-3 text-xs">
      <p className="text-fg font-medium">Legend</p>
      <ul className="space-y-1">
        {ACCENT_LABELS.map(([accent, label]) => (
          <li key={accent} className="flex items-center gap-2">
            <span
              aria-hidden
              className="h-3 w-1 rounded-full"
              style={{ backgroundColor: ACCENT_VAR[accent] }}
            />
            {label}
          </li>
        ))}
      </ul>
      <p className="flex items-center gap-2">
        <span
          aria-hidden
          className="w-6 border-t-2 border-dashed"
          style={{ borderColor: "var(--edge-llm)" }}
        />
        Request-time LLM call
      </p>
      <ul className="border-line space-y-1 border-t pt-2">
        {STATUS_LEGEND.map(([dot, label]) => (
          <li key={label} className="flex items-center gap-2">
            <span aria-hidden className={`size-2 rounded-full ${dot}`} />
            {label}
          </li>
        ))}
      </ul>
    </div>
  );
}
