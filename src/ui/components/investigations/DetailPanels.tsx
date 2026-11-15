"use client";

import { ExternalLink } from "lucide-react";
import { BreakdownList } from "@/components/investigations/EvidenceDrawer";
import { SourceLink } from "@/components/investigations/SourceLink";
import { ScoreRadar } from "@/components/charts/ScoreRadar";
import { Timeline } from "@/components/charts/Timeline";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import { DataPanel } from "@/components/ui/panel-state";
import { PhaseBadge } from "@/components/ui/phase-badge";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { usePublications } from "@/lib/api/hooks";
import type { InvestigationDetail, Lens } from "@/lib/api/types";
import { LENSES, LENS_LABELS } from "@/lib/constants";
import {
  formatBytes,
  formatConfidence,
  formatFlowRange,
  formatLabel,
  formatOxygenRange,
  formatPressureRange,
  formatScore,
  NOT_AVAILABLE,
} from "@/lib/format";

export function SummaryPanel({ detail }: { detail: InvestigationDetail }) {
  const { card } = detail;
  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
      <div className="space-y-4 xl:col-span-2">
        <Card>
          <CardHeader title="Summary" />
          <p className="text-muted text-sm">{detail.summary ?? "No curated summary yet."}</p>
          {card.approach ? (
            <div className="mt-4 space-y-1">
              <p className="text-muted text-xs font-medium tracking-wide uppercase">Approach</p>
              <p className="text-muted text-sm">{card.approach.text}</p>
              <SourceLink source={card.approach.source} />
            </div>
          ) : null}
        </Card>
        <Card>
          <CardHeader title="Objectives" />
          {card.objectives.length === 0 ? (
            <p className="text-muted text-sm">No objectives recorded.</p>
          ) : (
            <ul className="space-y-3">
              {card.objectives.map((objective) => (
                <li key={objective.text} className="space-y-1">
                  <p className="text-sm">{objective.text}</p>
                  <SourceLink source={objective.source} />
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card>
          <CardHeader title="Findings" />
          {detail.findings.length === 0 ? (
            <p className="text-muted text-sm">No findings recorded.</p>
          ) : (
            <ul className="space-y-4">
              {detail.findings.map((finding) => (
                <li key={finding.id} className="space-y-1">
                  <p className="text-sm">{finding.statement}</p>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge>{formatLabel(finding.category)}</Badge>
                    <span className="mono text-muted text-xs">
                      confidence {formatConfidence(finding.confidence)}
                    </span>
                    <SourceLink source={finding.source} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
      <div className="space-y-4">
        <ConditionsCard detail={detail} />
        <Card>
          <CardHeader title="Phenomena" />
          <div className="flex flex-wrap gap-1.5">
            {detail.fire_safety_tags.length === 0 ? (
              <span className="text-muted text-sm">None tagged.</span>
            ) : null}
            {detail.fire_safety_tags.map((tag) => (
              <Badge key={tag}>{formatLabel(tag)}</Badge>
            ))}
          </div>
        </Card>
        {card.open_questions.length ? (
          <Card>
            <CardHeader title="Open questions" description="Values the sources did not state." />
            <ul className="text-caption text-muted list-disc space-y-1 pl-5">
              {card.open_questions.map((question) => (
                <li key={question}>{question}</li>
              ))}
            </ul>
          </Card>
        ) : null}
      </div>
    </div>
  );
}

function ConditionsCard({ detail }: { detail: InvestigationDetail }) {
  const rows: [string, string][] = [
    ["Oxygen", formatOxygenRange(detail.o2_range)],
    ["Pressure", formatPressureRange(detail.pressure_range_kpa)],
    ["Flow", formatFlowRange(detail.flow_range_cm_s)],
    ["Gravity", detail.gravity_level ? formatLabel(detail.gravity_level) : NOT_AVAILABLE],
    ["Platform", detail.platform ?? NOT_AVAILABLE],
    ["Project", detail.project ?? NOT_AVAILABLE],
  ];
  return (
    <Card>
      <CardHeader title="Conditions" />
      <dl className="space-y-2">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-3 text-sm">
            <dt className="text-muted">{label}</dt>
            <dd className="mono text-right">{value}</dd>
          </div>
        ))}
      </dl>
      <div className="mt-4 flex flex-wrap gap-1.5">
        {detail.fuel_phases.map((phase) => (
          <PhaseBadge key={phase} phase={phase} />
        ))}
        {detail.hardware.map((name) => (
          <Badge key={name} tone="cool">
            {name}
          </Badge>
        ))}
      </div>
    </Card>
  );
}

export function MeasurementsPanel({ detail }: { detail: InvestigationDetail }) {
  if (detail.measurements.length === 0)
    return <p className="text-muted text-sm">No measurements are recorded.</p>;
  return (
    <Table label="Investigation details">
      <thead>
        <tr>
          {["Instrument", "Quantity", "Units", "File pattern", "Source"].map((h) => (
            <Th key={h}>{h}</Th>
          ))}
        </tr>
      </thead>
      <tbody>
        {detail.measurements.map((measurement, index) => (
          <Tr key={`${measurement.instrument}-${index}`}>
            <Td className="font-medium">{measurement.instrument}</Td>
            <Td>{measurement.quantity}</Td>
            <Td className="mono">{measurement.units ?? NOT_AVAILABLE}</Td>
            <Td className="mono">{measurement.file_pattern ?? NOT_AVAILABLE}</Td>
            <Td>
              {measurement.source ? <SourceLink source={measurement.source} /> : NOT_AVAILABLE}
            </Td>
          </Tr>
        ))}
      </tbody>
    </Table>
  );
}

export function PublicationsPanel({ id }: { id: string }) {
  const publications = usePublications(id);
  return (
    <DataPanel
      query={publications}
      isEmpty={(items) => items.length === 0}
      emptyMessage="No publications are linked yet."
    >
      {(items) => {
        const years = new Map<number, number>();
        items.forEach((item) => item.year && years.set(item.year, (years.get(item.year) ?? 0) + 1));
        const points = [...years]
          .sort(([a], [b]) => a - b)
          .map(([year, count]) => ({ year, count }));
        return (
          <div className="space-y-4">
            {points.length > 1 ? (
              <Card>
                <CardHeader title="Publications per year" />
                <Timeline points={points} label="Publications" />
              </Card>
            ) : null}
            <ul className="space-y-3">
              {items.map((item) => (
                <li key={`${item.doi ?? item.title}`}>
                  <Card className="space-y-1.5">
                    <p className="text-sm font-medium">{item.title}</p>
                    <p className="text-caption text-muted">
                      {[item.authors.join(", "), item.year, item.venue]
                        .filter(Boolean)
                        .join(" · ") || "Bibliographic details not stated."}
                    </p>
                    {item.url || item.doi ? (
                      <a
                        className="text-cool inline-flex items-center gap-1 text-xs hover:underline"
                        target="_blank"
                        rel="noopener noreferrer"
                        href={item.url ?? `https://doi.org/${item.doi}`}
                      >
                        {item.doi ?? "Open publication"}{" "}
                        <ExternalLink className="size-3" aria-hidden />
                      </a>
                    ) : null}
                  </Card>
                </li>
              ))}
            </ul>
          </div>
        );
      }}
    </DataPanel>
  );
}

export function ScoresPanel({ detail }: { detail: InvestigationDetail }) {
  const points = LENSES.flatMap((lens) => {
    const score = detail.score_breakdown[lens]?.score;
    return score === null || score === undefined ? [] : [{ axis: LENS_LABELS[lens], value: score }];
  });
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[360px_minmax(0,1fr)]">
        <Card className="lg:sticky lg:top-4 lg:self-start">
          <CardHeader
            title="Lens scores"
            description={`Overall ${formatScore(detail.scores.overall)} / 100`}
          />
          {points.length >= 3 ? (
            <ScoreRadar points={points} />
          ) : (
            <p className="text-muted text-sm">Radar needs three scored lenses.</p>
          )}
        </Card>
        <div className="space-y-4">
          {(LENSES as readonly Lens[]).map((lens) => {
            const entry = detail.score_breakdown[lens];
            return (
              <Card key={lens}>
                <CardHeader
                  title={`${LENS_LABELS[lens]} lens`}
                  description={
                    entry
                      ? `Score ${formatScore(entry.score)} / 100, confidence ${formatConfidence(entry.confidence)}`
                      : "Not scored"
                  }
                />
                {entry ? <BreakdownList breakdown={entry.breakdown} /> : null}
              </Card>
            );
          })}
        </div>
      </div>
      <p className="text-muted text-xs">
        Scores are relative decision aids, not safety certifications.
      </p>
    </div>
  );
}

export function DataFilesPanel({ detail }: { detail: InvestigationDetail }) {
  const rows: [string, string][] = [
    ["S3 prefix", detail.data.s3_prefix ?? NOT_AVAILABLE],
    ["Data volume", formatBytes(detail.data.volume_bytes)],
    [
      "File types",
      detail.data.file_types.length ? detail.data.file_types.join(", ") : NOT_AVAILABLE,
    ],
    ["Test runs", String(detail.run_count)],
  ];
  return (
    <Card className="max-w-2xl">
      <CardHeader
        title="Data in PSI"
        description="FlameScope links to raw data; it does not mirror it."
      />
      <dl className="space-y-2">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between gap-4 text-sm">
            <dt className="text-muted">{label}</dt>
            <dd className="mono text-right break-all">{value}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}
