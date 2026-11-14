import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type Tone = "success" | "warning" | "danger" | "neutral";

const STATUS_TONES: Record<string, Tone> = {
  up: "success",
  ready: "success",
  mock: "warning",
  idle: "warning",
  down: "danger",
};

const DOT_CLASS: Record<Tone, string> = {
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  neutral: "bg-faint",
};

export function statusTone(status: string | undefined): Tone {
  return (status && STATUS_TONES[status]) || "neutral";
}

interface StatusBadgeProps {
  status: string | undefined;
  label?: string;
  className?: string;
}

/** Colour dot plus text label so the state is never conveyed by colour alone. */
export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  const tone = statusTone(status);
  return (
    <Badge tone={tone} className={className} data-status={status ?? "unknown"}>
      <span aria-hidden className={cn("size-1.5 rounded-full", DOT_CLASS[tone])} />
      {label ?? status ?? "unknown"}
    </Badge>
  );
}
