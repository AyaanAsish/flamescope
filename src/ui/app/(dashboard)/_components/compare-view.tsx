"use client";

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

export function CompareView() {
  const { params, patch } = useUrlState();
  const setSelection = useUiStore((state) => state.setCompareSelection);
  const ids = parseList(params.get("ids")).slice(0, COMPARE_MAX);
  const isReady = ids.length >= COMPARE_MIN;
  const fast = useCompare({ investigations: ids, narrative: false }, isReady);
  const withNarrative = useCompare({ investigations: ids, narrative: true }, isReady);

  const change = (next: string[]) => {
    setSelection(next);
    patch({ ids: next.join(",") });
  };

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
