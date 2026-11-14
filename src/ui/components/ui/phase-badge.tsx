import { PHASE_COLORS, PHASE_LABELS } from "@/lib/constants";
import type { FuelPhase } from "@/lib/api/types";

const PHASE_SHAPE: Record<FuelPhase, string> = {
  gas: "rounded-full",
  liquid: "rotate-45 rounded-[2px]",
  solid: "rounded-[2px]",
};

function isPhase(value: string): value is FuelPhase {
  return value === "gas" || value === "liquid" || value === "solid";
}

/** Fuel-phase badge: colour plus marker shape plus text label. */
export function PhaseBadge({ phase }: { phase: string }) {
  if (!isPhase(phase)) {
    return <span className="text-muted text-xs">{phase}</span>;
  }
  return (
    <span className="rounded-control border-line bg-surface2 text-fg inline-flex items-center gap-1.5 border px-2 py-0.5 text-xs font-medium">
      <span
        aria-hidden
        className={`size-2 ${PHASE_SHAPE[phase]}`}
        style={{ backgroundColor: PHASE_COLORS[phase] }}
      />
      {PHASE_LABELS[phase]}
    </span>
  );
}
