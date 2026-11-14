"use client";

import { Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useExtractExport } from "@/lib/api/hooks";
import type { ExportFormat, ExtractRequest } from "@/lib/api/types";

const FORMATS: { format: ExportFormat; testId: string }[] = [
  { format: "csv", testId: "export-csv" },
  { format: "json", testId: "export-json" },
];

export function ExportButtons({ request }: { request: ExtractRequest }) {
  const exporter = useExtractExport();
  return (
    <div className="flex flex-wrap items-center gap-2">
      {FORMATS.map(({ format, testId }) => (
        <Button
          key={format}
          variant={format === "csv" ? "primary" : "secondary"}
          data-testid={testId}
          disabled={exporter.isPending}
          onClick={() => exporter.mutate({ ...request, format })}
        >
          <Download className="size-4" aria-hidden /> Export {format.toUpperCase()}
        </Button>
      ))}
      {exporter.isError ? (
        <span role="alert" className="text-caption text-danger">
          Export failed: {exporter.error.message}
        </span>
      ) : null}
    </div>
  );
}
