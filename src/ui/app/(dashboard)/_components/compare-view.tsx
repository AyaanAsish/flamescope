"use client";

import { useCallback, useEffect } from "react";

import { ComparePicker } from "@/components/compare/ComparePicker";
import { DiffMatrix } from "@/components/compare/DiffMatrix";
import { LineageGraph } from "@/components/compare/LineageGraph";
import { NarrativePanel } from "@/components/compare/NarrativePanel";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import { DataPanel } from "@/components/ui/panel-state";
import { SkeletonRows } from "@/components/ui/skeleton";
import { useCompare } from "@/lib/api/hooks";
import type { CompareResponse, Narrative } from "@/lib/api/types";
import { COMPARE_MAX, COMPARE_MIN } from "@/lib/constants";
import { useUiStore } from "@/lib/store";
import { parseList, useUrlState } from "@/lib/use-url-state";

function SharedFacts({ shared }: { shared: CompareResponse["shared"] }) {
  const groups: [string, string[]][] = [
    ["Shared hardware", shared.hardware],
    ["Shared phenomena", shared.tags],
    ["Shared instruments", shared.instruments],
  ];
  return (
    <Card>
      <CardHeader title="Shared" description="What every selected investigation has in common." />
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {groups.map(([title, values]) => (
          <div key={title}>
            <p className="text-muted mb-1.5 text-xs font-medium tracking-wide uppercase">{title}</p>
            <div className="flex flex-wrap gap-1.5">
              {values.length === 0 ? (
                <span className="text-muted text-sm">None</span>
              ) : (
                values.map((value) => <Badge key={value}>{value}</Badge>)
              )}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

const UNAVAILABLE_NARRATIVE: Narrative = { text: "", sentences: [], status: "unavailable" };

function narrativeOf(query: { data?: CompareResponse; isError: boolean }): Narrative | undefined {
  if (query.data) return query.data.narrative;
  return query.isError ? UNAVAILABLE_NARRATIVE : undefined;
}

/** The URL wins; without `ids` the selection made on Explorer cards is used and mirrored. */
function useCompareIds(): { ids: string[]; change: (next: string[]) => void } {
  const { params, patch } = useUrlState();
  const stored = useUiStore((state) => state.compareSelection);
  const setSelection = useUiStore((state) => state.setCompareSelection);
  const fromUrl = parseList(params.get("ids"));
  const ids = (fromUrl.length > 0 ? fromUrl : stored).slice(0, COMPARE_MAX);
  const shouldMirror = fromUrl.length === 0 && stored.length > 0;
  const mirrored = stored.join(",");

  useEffect(() => {
    if (shouldMirror) patch({ ids: mirrored });
  }, [shouldMirror, mirrored, patch]);

  const change = useCallback(
    (next: string[]) => {
      setSelection(next);
      patch({ ids: next.join(",") });
    },
    [setSelection, patch],
  );
  return { ids, change };
}

/**
 * Acronym keys are case-insensitive (doc 05 s4); the lineage graph and the picker match the
 * exact acronym, so the URL spelling is replaced by the one the compare response returns.
 */
function useCanonicalIds(
  ids: string[],
  response: CompareResponse | undefined,
  change: (next: string[]) => void,
): void {
  const canonical = response?.investigations.map((item) => item.acronym) ?? [];
  const isSameSelection =
    canonical.length === ids.length &&
    canonical.every((acronym, index) => acronym.toLowerCase() === ids[index]?.toLowerCase());
  const needsRewrite = isSameSelection && canonical.join(",") !== ids.join(",");
  const target = canonical.join(",");

  useEffect(() => {
    if (needsRewrite) change(target.split(","));
  }, [needsRewrite, target, change]);
}

export function CompareView() {
  const { ids, change } = useCompareIds();
  const isReady = ids.length >= COMPARE_MIN;
  const fast = useCompare({ investigations: ids, narrative: false }, isReady);
  const withNarrative = useCompare({ investigations: ids, narrative: true }, isReady);
  useCanonicalIds(ids, fast.data, change);

  return (
    <>
      <PageHeader
        title="Compare"
        description="Side-by-side differences in fuel, atmosphere, hardware and measurements, with a cited narrative."
      />
      <div className="space-y-6">
        <ComparePicker selected={ids} onChange={change} />
        {isReady ? (
          <>
            <DataPanel
              query={fast}
              skeleton={<SkeletonRows rows={8} />}
              isEmpty={(data) => data.matrix.length === 0}
              emptyMessage="Nothing to compare for this selection."
            >
              {(data) => (
                <div className="space-y-6">
                  <DiffMatrix
                    rows={data.matrix}
                    acronyms={data.investigations.map((item) => item.acronym)}
                  />
                  <SharedFacts shared={data.shared} />
                </div>
              )}
            </DataPanel>
            <NarrativePanel
              testId="compare-narrative"
              narrative={narrativeOf(withNarrative)}
              isLoading={withNarrative.isPending && !withNarrative.isError}
            />
            <LineageGraph acronyms={ids} />
          </>
        ) : (
          <Card>
            <p className="text-muted py-8 text-center text-sm" data-testid="diff-matrix">
              Choose at least {COMPARE_MIN} investigations to see how they differ.
            </p>
          </Card>
        )}
      </div>
    </>
  );
}
