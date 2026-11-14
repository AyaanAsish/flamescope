"use client";

import { DataPanel } from "@/components/ui/panel-state";
import { SkeletonRows } from "@/components/ui/skeleton";
import { Table, Td, Th } from "@/components/ui/table";
import type { ColumnInfo, ExtractRequest, Table as ExtractTable } from "@/lib/api/types";
import { useExtractPreview } from "@/lib/api/hooks";
import { formatCell, formatOxygen, NOT_AVAILABLE } from "@/lib/format";

const O2_COLUMN = "o2_fraction";

function columnHeader(column: ColumnInfo): string {
  if (column.name === O2_COLUMN) return `${column.label} (%)`;
  return column.unit ? `${column.label} (${column.unit})` : column.label;
}

export function formatExtractCell(column: ColumnInfo, value: unknown): string {
  if (column.name === O2_COLUMN && typeof value === "number")
    return formatOxygen(value).replace(" % O₂", "");
  if (value === null || value === undefined) return NOT_AVAILABLE;
  return formatCell(value);
}

function Rows({ table }: { table: ExtractTable }) {
  return (
    <>
      <Table>
        <thead>
          <tr>
            {table.columns.map((column) => (
              <Th key={column.name}>{columnHeader(column)}</Th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, rowIndex) => (
            <tr key={rowIndex} className="hover:bg-surface2/60">
              {table.columns.map((column, columnIndex) => (
                <Td key={column.name} className="mono whitespace-nowrap">
                  {formatExtractCell(column, row[columnIndex])}
                </Td>
              ))}
            </tr>
          ))}
        </tbody>
      </Table>
      <p className="text-muted mt-2 text-xs">
        Showing {table.rows.length} of {table.total} runs. Missing values are unknown, not zero.
      </p>
    </>
  );
}

export function PreviewTable({ request }: { request: ExtractRequest }) {
  const preview = useExtractPreview(request);
  return (
    <DataPanel
      query={preview}
      testId="extract-preview"
      skeleton={<SkeletonRows rows={8} />}
      isEmpty={(table) => table.rows.length === 0}
      emptyMessage="No test runs match this query. Loosen a filter."
    >
      {(table) => <Rows table={table} />}
    </DataPanel>
  );
}
