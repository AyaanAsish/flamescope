"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Pagination } from "@/components/ui/pagination";
import { DataPanel } from "@/components/ui/panel-state";
import { PhaseBadge } from "@/components/ui/phase-badge";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { SourceLink } from "@/components/investigations/SourceLink";
import { useRuns } from "@/lib/api/hooks";
import type { RunItem } from "@/lib/api/types";
import {
  formatConfidence,
  formatFlow,
  formatGravity,
  formatOxygen,
  formatPressure,
  formatSpreadRate,
  NOT_AVAILABLE,
} from "@/lib/format";

// Doc 05 section 1 maximum page size; larger investigations page through their runs.
const RUNS_PAGE_SIZE = 100;
const FIRST_PAGE = 1;

const HEADERS = [
  "Run",
  "Fuel",
  "Oxygen",
  "Pressure",
  "Flow",
  "Direction",
  "Gravity",
  "Spread rate",
  "Ignited",
  "Confidence",
  "Source",
];

function yesNo(value: boolean | null): string {
  if (value === null) return NOT_AVAILABLE;
  return value ? "yes" : "no";
}

function RunRow({ run }: { run: RunItem }) {
  const { condition, outcome } = run;
  return (
    <Tr>
      <Td>
        <span className="font-medium">{run.label}</span>
        {run.is_aggregate ? (
          <Badge className="ml-2" tone="warning">
            Stated range
          </Badge>
        ) : null}
      </Td>
      <Td>
        {run.fuel ? (
          <span className="flex items-center gap-2">
            {run.fuel.name} <PhaseBadge phase={run.fuel.phase} />
          </span>
        ) : (
          NOT_AVAILABLE
        )}
      </Td>
      <Td className="mono">{formatOxygen(condition.o2_fraction)}</Td>
      <Td className="mono">{formatPressure(condition.pressure_kpa)}</Td>
      <Td className="mono">{formatFlow(condition.flow_speed_cm_s)}</Td>
      <Td>{condition.flow_direction ?? NOT_AVAILABLE}</Td>
      <Td className="mono">{formatGravity(condition.gravity_g)}</Td>
      <Td className="mono">{formatSpreadRate(outcome.flame_spread_rate_mm_s)}</Td>
      <Td>{yesNo(outcome.ignited)}</Td>
      <Td className="mono">{formatConfidence(run.confidence)}</Td>
      <Td className="max-w-48">
        {run.source ? <SourceLink source={run.source} /> : NOT_AVAILABLE}
      </Td>
    </Tr>
  );
}

export function RunsTable({ id }: { id: string }) {
  const [pageNumber, setPageNumber] = useState(FIRST_PAGE);
  const runs = useRuns(id, pageNumber, RUNS_PAGE_SIZE);
  return (
    <DataPanel
      query={runs}
      testId="runs-table"
      isEmpty={(page) => page.items.length === 0}
      emptyMessage="No test runs are recorded for this investigation."
    >
      {(page) => (
        <>
          <Table label="Test runs">
            <thead>
              <tr>
                {HEADERS.map((header) => (
                  <Th key={header}>{header}</Th>
                ))}
              </tr>
            </thead>
            <tbody>
              {page.items.map((run) => (
                <RunRow key={run.id} run={run} />
              ))}
            </tbody>
          </Table>
          <p className="text-muted mt-2 text-xs">
            Showing {page.items.length} of {page.total} runs. Missing values are unknown, not zero.
          </p>
          {page.total > page.page_size ? (
            <Pagination
              page={page.page}
              pageSize={page.page_size}
              total={page.total}
              onPageChange={setPageNumber}
            />
          ) : null}
        </>
      )}
    </DataPanel>
  );
}
