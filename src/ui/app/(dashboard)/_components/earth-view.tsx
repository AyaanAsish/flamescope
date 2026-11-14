"use client";

import Link from "next/link";
import { SourceLink } from "@/components/investigations/SourceLink";
import { PageHeader } from "@/components/layout/PageHeader";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { DataPanel } from "@/components/ui/panel-state";
import { SkeletonRows } from "@/components/ui/skeleton";
import { useEarthApplications } from "@/lib/api/hooks";
import type { EarthApplicationOut, EarthSector } from "@/lib/api/types";
import { EARTH_SECTORS } from "@/lib/constants";
import { formatLabel } from "@/lib/format";
import { useUrlState } from "@/lib/use-url-state";

function EarthCard({ application }: { application: EarthApplicationOut }) {
  return (
    <Card data-testid="earth-card" className="flex flex-col gap-3">
      <div className="flex items-start justify-between gap-3">
        <h2 className="text-base font-semibold">{application.title}</h2>
        <Badge tone="accent">{formatLabel(application.sector)}</Badge>
      </div>
      <p className="text-muted text-sm">{application.description}</p>
      {application.maturity ? (
        <p className="text-caption text-muted">Maturity: {application.maturity}</p>
      ) : null}
      {application.investigations.length ? (
        <div>
          <p className="text-muted mb-1 text-xs font-medium tracking-wide uppercase">
            Linked investigations
          </p>
          <div className="flex flex-wrap gap-1.5">
            {application.investigations.map((acronym) => (
              <Link key={acronym} href={`/investigations/${encodeURIComponent(acronym)}`}>
                <Badge tone="cool">{acronym}</Badge>
              </Link>
            ))}
          </div>
        </div>
      ) : null}
      {application.references.length ? (
        <ul className="border-line space-y-1 border-t pt-3">
          {application.references.map((reference, index) => (
            <li key={`${reference.uri}-${index}`}>
              <SourceLink source={reference} />
            </li>
          ))}
        </ul>
      ) : null}
    </Card>
  );
}

function SectorFilter({
  sector,
  onChange,
}: {
  sector: EarthSector | undefined;
  onChange: (sector: EarthSector | null) => void;
}) {
  return (
    <div role="group" aria-label="Sector" className="mb-6 flex flex-wrap gap-2">
      <Button
        size="sm"
        variant={sector ? "secondary" : "primary"}
        aria-pressed={!sector}
        onClick={() => onChange(null)}
      >
        All sectors
      </Button>
      {EARTH_SECTORS.map((item) => (
        <Button
          key={item}
          size="sm"
          variant={sector === item ? "primary" : "secondary"}
          aria-pressed={sector === item}
          onClick={() => onChange(item)}
        >
          {formatLabel(item)}
        </Button>
      ))}
    </div>
  );
}

export function EarthView() {
  const { params, patch } = useUrlState();
  const raw = params.get("sector");
  const sector = EARTH_SECTORS.find((item) => item === raw);
  const applications = useEarthApplications(sector);
  return (
    <>
      <PageHeader
        title="Earth Apps"
        description="How microgravity combustion findings inform fire safety on Earth. Applications are curated and reviewed before they appear here."
      />
      <SectorFilter sector={sector} onChange={(next) => patch({ sector: next })} />
      <DataPanel
        query={applications}
        skeleton={<SkeletonRows rows={6} />}
        isEmpty={(data) => data.items.length === 0}
        emptyMessage="No Earth applications are listed for this sector."
      >
        {(data) => (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 2xl:grid-cols-3">
            {data.items.map((application) => (
              <EarthCard key={application.id} application={application} />
            ))}
          </div>
        )}
      </DataPanel>
    </>
  );
}
