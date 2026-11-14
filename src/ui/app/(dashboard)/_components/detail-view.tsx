"use client";

import { ExternalLink } from "lucide-react";
import Link from "next/link";
import { DetailTabs } from "@/components/investigations/DetailTabs";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { DataPanel } from "@/components/ui/panel-state";
import { PhaseBadge } from "@/components/ui/phase-badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useInvestigation } from "@/lib/api/hooks";
import type { InvestigationDetail } from "@/lib/api/types";
import { formatLabel } from "@/lib/format";

function DetailHeader({ detail }: { detail: InvestigationDetail }) {
  return (
    <header data-testid="detail-header" className="mb-6">
      <Link href="/explorer" className="text-caption text-muted hover:text-fg">
        Explorer
      </Link>
      <PageHeader
        title={detail.acronym}
        description={detail.title}
        actions={
          detail.psi_url ? (
            <a
              href={detail.psi_url}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-control border-line bg-surface2 hover:border-line-strong inline-flex h-9 items-center gap-2 border px-4 text-sm font-medium"
            >
              View in PSI <ExternalLink className="size-3.5" aria-hidden />
            </a>
          ) : null
        }
      />
      <div className="-mt-3 flex flex-wrap gap-2">
        {detail.fuel_phases.map((phase) => (
          <PhaseBadge key={phase} phase={phase} />
        ))}
        {detail.platform ? <Badge>{detail.platform}</Badge> : null}
        {detail.gravity_level ? (
          <Badge tone="cool">{formatLabel(detail.gravity_level)}</Badge>
        ) : null}
        <Badge tone={detail.reviewed ? "success" : "neutral"}>
          {detail.reviewed ? "Reviewed" : "Unreviewed"}
        </Badge>
        <Badge>{detail.run_count} test runs</Badge>
      </div>
    </header>
  );
}

export function DetailView({ id }: { id: string }) {
  const query = useInvestigation(id);
  return (
    <DataPanel
      query={query}
      skeleton={
        <div data-testid="detail-header" className="space-y-4">
          <Skeleton className="h-10 w-64" />
          <Skeleton className="h-96" />
        </div>
      }
    >
      {(detail) => (
        <>
          <DetailHeader detail={detail} />
          <DetailTabs detail={detail} />
        </>
      )}
    </DataPanel>
  );
}
