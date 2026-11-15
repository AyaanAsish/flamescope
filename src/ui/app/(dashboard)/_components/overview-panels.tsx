"use client";

import { ArrowRight } from "lucide-react";
import Link from "next/link";
import {
  ParameterSpaceScatter,
  type ScatterPoint,
} from "@/components/charts/ParameterSpaceScatter";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import { DataPanel } from "@/components/ui/panel-state";
import { SkeletonRows, Skeleton } from "@/components/ui/skeleton";
import { StatTile } from "@/components/ui/stat-tile";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { useExtractPreview, useGaps, useRank, useStats } from "@/lib/api/hooks";
import type { FuelPhase, StatsResponse, Table as ExtractTable } from "@/lib/api/types";
import {
  FUEL_PHASES,
  OVERVIEW_SCATTER_LIMIT,
  OVERVIEW_TOP_LIMIT,
  PHASE_LABELS,
} from "@/lib/constants";
import {
  formatCount,
  formatOxygenRange,
  formatPressureRange,
  formatScore,
  formatConfidence,
  fractionToPercent,
} from "@/lib/format";

const SCATTER_COLUMNS = ["o2_fraction", "pressure_kpa", "fuel_phase", "investigation"];

function StatsSkeleton() {
  return (
    <div className="grid grid-cols-2 gap-4 lg:grid-cols-6">
      {Array.from({ length: 6 }, (_, index) => (
        <Skeleton key={index} className="h-24" />
      ))}
    </div>
  );
}

function StatTiles({ stats }: { stats: StatsResponse }) {
  const phases = FUEL_PHASES.map(
    (phase) => `${stats.fuel_phase_counts[phase] ?? 0} ${PHASE_LABELS[phase].toLowerCase()}`,
  );
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-6">
        <StatTile
          label="Investigations"
          value={formatCount(stats.investigations)}
          hint={phases.join(", ")}
        />
        <StatTile label="Test runs" value={formatCount(stats.test_runs)} />
        <StatTile label="Publications" value={formatCount(stats.publications)} />
        <StatTile label="Findings" value={formatCount(stats.findings)} />
        <StatTile label="Indexed chunks" value={formatCount(stats.chunks)} />
        <StatTile label="Hardware" value={formatCount(stats.hardware)} />
      </div>
      <p className="text-caption text-muted">
        Catalog covers oxygen {formatOxygenRange(stats.o2_range)} and pressure{" "}
        {formatPressureRange(stats.pressure_range_kpa)}.
      </p>
    </div>
  );
}

export function OverviewStats() {
  const stats = useStats();
  return (
    <DataPanel query={stats} testId="overview-stats" skeleton={<StatsSkeleton />}>
      {(data) => <StatTiles stats={data} />}
    </DataPanel>
  );
}

function toScatterPoints(table: ExtractTable): ScatterPoint[] {
  const index = (name: string) => table.columns.findIndex((column) => column.name === name);
  const [o2, pressure, phase, investigation] = SCATTER_COLUMNS.map(index);
  const points: ScatterPoint[] = [];
  for (const row of table.rows) {
    const o2Value = row[o2 ?? -1];
    const pressureValue = row[pressure ?? -1];
    const phaseValue = row[phase ?? -1];
    if (typeof o2Value !== "number" || typeof pressureValue !== "number") continue;
    if (!FUEL_PHASES.includes(phaseValue as FuelPhase)) continue;
    points.push({
      o2Percent: fractionToPercent(o2Value),
      pressureKpa: pressureValue,
      phase: phaseValue as FuelPhase,
      investigation: String(row[investigation ?? -1] ?? ""),
    });
  }
  return points;
}

export function OverviewScatter() {
  const preview = useExtractPreview({
    filters: {},
    columns: SCATTER_COLUMNS,
    limit: OVERVIEW_SCATTER_LIMIT,
  });
  return (
    <Card>
      <CardHeader
        title="Parameter-space coverage"
        description="Test runs by oxygen concentration and pressure, coloured by fuel phase. The shaded region is the lunar-habitat envelope (30 % O2 or more, 70.3 kPa or less)."
      />
      <DataPanel
        query={preview}
        testId="overview-scatter"
        isEmpty={(table) => table.rows.length === 0}
        emptyMessage="No test runs with oxygen and pressure values are available yet."
        skeleton={<Skeleton className="h-80" />}
      >
        {(table) => <ParameterSpaceScatter points={toScatterPoints(table)} />}
      </DataPanel>
    </Card>
  );
}

export function OverviewTop() {
  const rank = useRank({ lens: "overall", limit: OVERVIEW_TOP_LIMIT });
  return (
    <Card>
      <CardHeader
        title="Top 5 overall"
        description="Highest relative relevance across the three lenses with default weights."
        action={
          <Link
            href="/ranking"
            className="text-caption text-cool flex items-center gap-1 hover:underline"
          >
            Full ranking <ArrowRight className="size-3.5" aria-hidden />
          </Link>
        }
      />
      <DataPanel
        query={rank}
        testId="overview-top"
        isEmpty={(data) => data.items.length === 0}
        emptyMessage="No ranked investigations yet."
        skeleton={<SkeletonRows rows={5} />}
      >
        {(data) => (
          <Table label="Top-ranked investigations" className="table-fixed">
            <thead>
              <tr>
                <Th className="w-10">#</Th>
                <Th>Investigation</Th>
                <Th className="w-32 text-right">Score (0-100)</Th>
                <Th className="w-32 text-right">Confidence</Th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item) => (
                <Tr key={item.acronym}>
                  <Td className="mono text-muted">{item.rank}</Td>
                  <Td>
                    <Link
                      href={`/investigations/${encodeURIComponent(item.acronym)}`}
                      className="hover:text-accent font-medium"
                    >
                      {item.acronym}
                    </Link>
                    <p className="text-muted truncate text-xs" title={item.title}>
                      {item.title}
                    </p>
                  </Td>
                  <Td className="mono text-right">{formatScore(item.score)}</Td>
                  <Td className="mono text-right">{formatConfidence(item.confidence)}</Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        )}
      </DataPanel>
    </Card>
  );
}

export function OverviewGaps() {
  const gaps = useGaps();
  return (
    <Card>
      <CardHeader
        title="Evidence gaps"
        description="Where the PSI catalog does not yet answer fire-safety questions."
      />
      <DataPanel
        query={gaps}
        testId="overview-gaps"
        isEmpty={(data) => data.gaps.length === 0}
        emptyMessage="No gaps reported."
        skeleton={<SkeletonRows rows={3} />}
      >
        {(data) => (
          <ul className="space-y-4">
            {data.gaps.slice(0, 4).map((gap) => (
              <li key={gap.id} className="space-y-1.5">
                <p className="font-medium">{gap.title}</p>
                <p className="text-caption text-muted">{gap.detail}</p>
                <div className="flex flex-wrap gap-1.5">
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

const QUICK_LINKS = [
  {
    href: "/scenario?preset=lunar_habitat",
    title: "Run a lunar-habitat scenario",
    body: "Match 34 % O2 at 56.5 kPa against the catalog.",
  },
  {
    href: "/ranking",
    title: "Rank by lens",
    body: "Habitat, modeling and controls relevance with tunable weights.",
  },
  {
    href: "/ask",
    title: "Ask the corpus",
    body: "Cited answers drawn only from curated PSI documents.",
  },
  {
    href: "/extract",
    title: "Extract test-run data",
    body: "Preview and export conditions and outcomes as CSV or JSON.",
  },
] as const;

export function QuickLinks() {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
      {QUICK_LINKS.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          className="group rounded-card border-line bg-surface1 hover:border-line-strong hover:bg-surface2 border p-4 transition-colors"
        >
          <p className="flex items-center justify-between font-medium">
            {link.title}
            <ArrowRight
              className="text-muted group-hover:text-accent size-4 transition-colors"
              aria-hidden
            />
          </p>
          <p className="text-caption text-muted mt-1">{link.body}</p>
        </Link>
      ))}
    </div>
  );
}

export function OverviewHero() {
  return (
    <section className="hero-glow rounded-card border-line mb-6 border p-8">
      <Badge tone="accent">NASA Space Apps 2026 - Flame in Freefall</Badge>
      <h1 className="mt-4 max-w-3xl text-3xl font-semibold tracking-tight">
        Combustion research from NASA PSI, ranked and interpreted for fire safety.
      </h1>
      <p className="text-muted mt-3 max-w-2xl text-sm">
        FlameScope curates NASA PSI combustion investigations into comparable cards, scores their
        relevance to habitat design, modeling and controls, and shows exactly where the evidence
        stops.
      </p>
    </section>
  );
}
