"use client";

import Link from "next/link";
import { SourceLink } from "@/components/investigations/SourceLink";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import { DataPanel } from "@/components/ui/panel-state";
import { SkeletonRows } from "@/components/ui/skeleton";
import { useGaps, useSafetyTech } from "@/lib/api/hooks";
import type { SafetyGroup } from "@/lib/api/types";
import { formatConfidence } from "@/lib/format";

function InvestigationLinks({ acronyms }: { acronyms: string[] }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {acronyms.map((acronym) => (
        <Link key={acronym} href={`/investigations/${encodeURIComponent(acronym)}`}>
          <Badge tone="cool" className="hover:border-cool">
            {acronym}
          </Badge>
        </Link>
      ))}
    </div>
  );
}

function SafetyGroupCard({ group }: { group: SafetyGroup }) {
  return (
    <Card data-testid="safety-group" data-category={group.category} className="space-y-4">
      <CardHeader
        title={group.label}
        description={`${group.findings.length} findings from ${group.investigations.length} investigations`}
      />
      <InvestigationLinks acronyms={group.investigations} />
      <ul className="space-y-4">
        {group.findings.map((finding) => (
          <li key={finding.id} className="border-line space-y-1 border-t pt-3">
            <p className="text-sm">{finding.statement}</p>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <Link href={`/investigations/${encodeURIComponent(finding.investigation)}`}>
                <Badge className="hover:border-cool">{finding.investigation}</Badge>
              </Link>
              <span className="mono text-muted text-xs">
                confidence {formatConfidence(finding.confidence)}
              </span>
              <SourceLink source={finding.source} />
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function GapsCard() {
  const gaps = useGaps();
  return (
    <Card>
      <CardHeader
        title="Gaps and future data"
        description="What the catalog cannot yet answer for equipment and controls design."
      />
      <DataPanel
        query={gaps}
        isEmpty={(data) => data.gaps.length === 0}
        emptyMessage="No gaps reported."
        skeleton={<SkeletonRows rows={3} />}
      >
        {(data) => (
          <ul className="space-y-4">
            {data.gaps.map((gap) => (
              <li key={gap.id} className="space-y-1.5">
                <p className="font-medium">{gap.title}</p>
                <p className="text-caption text-muted">{gap.detail}</p>
                <div className="flex flex-wrap items-center gap-1.5">
                  {gap.related.map((acronym) => (
                    <Badge key={acronym}>Related: {acronym}</Badge>
                  ))}
                  {gap.future.map((acronym) => (
                    <Badge key={acronym} tone="cool">
                      Expected: {acronym}
                    </Badge>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        )}
      </DataPanel>
    </Card>
  );
}

export function SafetyTechView() {
  const safety = useSafetyTech();
  return (
    <>
      <PageHeader
        title="Safety Tech"
        description="Findings grouped by the fire-safety function they inform, with the investigations that support them."
      />
      <div className="space-y-6">
        <DataPanel
          query={safety}
          skeleton={
            <div className="grid gap-4 lg:grid-cols-2">
              <SkeletonRows rows={5} />
              <SkeletonRows rows={5} />
            </div>
          }
          isEmpty={(data) => data.groups.length === 0}
          emptyMessage="No findings have been curated yet."
        >
          {(data) => (
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 2xl:grid-cols-3">
              {data.groups.map((group) => (
                <SafetyGroupCard key={group.category} group={group} />
              ))}
            </div>
          )}
        </DataPanel>
        <GapsCard />
      </div>
    </>
  );
}
