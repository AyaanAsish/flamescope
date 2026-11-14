import type { ReactNode } from "react";
import { Card } from "@/components/ui/card";

interface StatTileProps {
  label: string;
  value: ReactNode;
  hint?: string;
}

export function StatTile({ label, value, hint }: StatTileProps) {
  return (
    <Card className="p-4">
      <p className="text-muted text-xs font-medium tracking-wide uppercase">{label}</p>
      <p className="mono text-fg mt-1 text-3xl font-semibold">{value}</p>
      {hint ? <p className="text-muted mt-0.5 text-xs">{hint}</p> : null}
    </Card>
  );
}
