"use client";

import { GitCompareArrows } from "lucide-react";
import Link from "next/link";
import { InvestigationCard } from "@/components/investigations/InvestigationCard";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/input";
import { DataPanel } from "@/components/ui/panel-state";
import { Pagination } from "@/components/ui/pagination";
import { Skeleton } from "@/components/ui/skeleton";
import { useInvestigations } from "@/lib/api/hooks";
import type { FuelPhase, GravityLevel, InvestigationListParams, SortKey } from "@/lib/api/types";
import { EXPLORER_PAGE_SIZE, SORT_OPTIONS } from "@/lib/constants";
import { percentToFraction } from "@/lib/format";
import { useUiStore } from "@/lib/store";
import { parseList, parseNumber, useUrlState } from "@/lib/use-url-state";
import { ExplorerFilters } from "./explorer-filters";

function toApiParams(params: URLSearchParams): InvestigationListParams {
  const o2Min = parseNumber(params.get("o2_min"));
  const o2Max = parseNumber(params.get("o2_max"));
  return {
    q: params.get("q") ?? undefined,
    fuel_phase: parseList(params.get("fuel_phase")) as FuelPhase[],
    hardware: parseList(params.get("hardware")),
    tag: parseList(params.get("tag")),
    project: params.get("project") ?? undefined,
    gravity_level: (params.get("gravity_level") as GravityLevel | null) ?? undefined,
    o2_min: o2Min === undefined ? undefined : percentToFraction(o2Min),
    o2_max: o2Max === undefined ? undefined : percentToFraction(o2Max),
    pressure_min_kpa: parseNumber(params.get("pressure_min_kpa")),
    pressure_max_kpa: parseNumber(params.get("pressure_max_kpa")),
    sort: (params.get("sort") as SortKey | null) ?? "acronym",
    page: parseNumber(params.get("page")) ?? 1,
    page_size: EXPLORER_PAGE_SIZE,
  };
}

function CardGridSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2 2xl:grid-cols-3">
      {Array.from({ length: 6 }, (_, index) => (
        <Skeleton key={index} className="h-72" />
      ))}
    </div>
  );
}

export function ExplorerView() {
  const { params, patch } = useUrlState();
  const apiParams = toApiParams(params);
  const query = useInvestigations(apiParams);
  const selection = useUiStore((state) => state.compareSelection);
  const toggleCompare = useUiStore((state) => state.toggleCompare);

  return (
    <>
      <PageHeader
        title="Explorer"
        description="Browse the curated combustion investigations and filter by fuel, atmosphere, hardware and phenomenon."
        actions={
          <>
            <label className="sr-only" htmlFor="explorer-sort">
              Sort by
            </label>
            <Select
              id="explorer-sort"
              data-testid="explorer-sort"
              value={apiParams.sort}
              className="w-44"
              onChange={(event) => patch({ sort: event.target.value, page: null })}
            >
              {SORT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  Sort: {option.label}
                </option>
              ))}
            </Select>
            <Button asChild variant="primary" aria-disabled={selection.length < 2}>
              <Link href={`/compare?ids=${selection.map(encodeURIComponent).join(",")}`}>
                <GitCompareArrows className="size-4" aria-hidden /> Compare ({selection.length})
              </Link>
            </Button>
          </>
        }
      />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
        <ExplorerFilters />
        <section aria-label="Investigations">
          <DataPanel
            query={query}
            skeleton={<CardGridSkeleton />}
            isEmpty={(page) => page.items.length === 0}
            emptyMessage="No investigations match these filters. Clear a filter to widen the search."
          >
            {(page) => (
              <>
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 2xl:grid-cols-3">
                  {page.items.map((investigation) => (
                    <InvestigationCard
                      key={investigation.id}
                      investigation={investigation}
                      isSelectedForCompare={selection.includes(investigation.acronym)}
                      onToggleCompare={toggleCompare}
                    />
                  ))}
                </div>
                <Pagination
                  page={page.page}
                  pageSize={page.page_size}
                  total={page.total}
                  onPageChange={(next) => patch({ page: next })}
                />
              </>
            )}
          </DataPanel>
        </section>
      </div>
    </>
  );
}
