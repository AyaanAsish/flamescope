"use client";

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { RankLens } from "@/lib/api/types";
import { LENS_COLORS, LENS_LABELS, RANK_LENSES } from "@/lib/constants";

interface LensTabsProps {
  lens: RankLens;
  onLensChange: (lens: RankLens) => void;
}

export function LensTabs({ lens, onLensChange }: LensTabsProps) {
  return (
    <Tabs
      value={lens}
      onValueChange={(value) => onLensChange(value as RankLens)}
      data-testid="ranking-lens-tabs"
    >
      <TabsList aria-label="Ranking lens">
        {RANK_LENSES.map((item) => (
          // The lens tabs re-rank one shared table, so there is no tab panel to control.
          <TabsTrigger
            key={item}
            value={item}
            aria-controls={undefined}
            className="flex items-center gap-2"
          >
            {item === "overall" ? null : (
              <span
                aria-hidden
                className="size-2 rounded-full"
                style={{ backgroundColor: LENS_COLORS[item] }}
              />
            )}
            {LENS_LABELS[item]}
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  );
}
