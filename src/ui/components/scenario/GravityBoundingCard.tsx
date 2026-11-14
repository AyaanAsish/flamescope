"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import type { GravityBound, GravityBounding } from "@/lib/api/types";
import { formatGravity } from "@/lib/format";

function BoundRow({ title, bound }: { title: string; bound: GravityBound | null }) {
  return (
    <div className="rounded-control border-line bg-surface2/40 border p-3">
      <p className="text-muted text-xs font-medium tracking-wide uppercase">{title}</p>
      <p className="mono mt-0.5 text-sm">{bound ? formatGravity(bound.gravity_g) : "n/a"}</p>
      <p className="text-caption text-muted mt-1">
        {bound && bound.investigations.length > 0
          ? bound.investigations.join(", ")
          : "No matching investigations"}
      </p>
    </div>
  );
}

export function GravityBoundingCard({ bounding }: { bounding: GravityBounding }) {
  return (
    <Card data-testid="gravity-bounding">
      <CardHeader
        title="Gravity bounding"
        description="Partial gravity is bounded by microgravity and normal-gravity results, never interpolated."
        action={
          <Badge tone={bounding.partial_gravity_data ? "success" : "warning"}>
            {bounding.partial_gravity_data
              ? "Partial-gravity data present"
              : "No partial-gravity data"}
          </Badge>
        }
      />
      {bounding.statement ? <p className="text-muted text-sm">{bounding.statement}</p> : null}
      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
        <BoundRow title="Lower bound" bound={bounding.lower_bound} />
        <BoundRow title="Upper bound" bound={bounding.upper_bound} />
      </div>
      {bounding.analogue ? (
        <p className="text-caption text-muted mt-4">
          <span className="text-fg font-medium">Analogue: {bounding.analogue.acronym}.</span>{" "}
          {bounding.analogue.note}
        </p>
      ) : null}
    </Card>
  );
}
