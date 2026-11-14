"use client";

import { ColumnPicker } from "@/components/extract/ColumnPicker";
import { ExportButtons } from "@/components/extract/ExportButtons";
import { PreviewTable } from "@/components/extract/PreviewTable";
import { QueryBuilder } from "@/components/extract/QueryBuilder";
import { readExtractRequest } from "@/components/extract/extract-state";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardHeader } from "@/components/ui/card";
import { useUrlState } from "@/lib/use-url-state";

export function ExtractView() {
  const { params } = useUrlState();
  const request = readExtractRequest(params);
  return (
    <>
      <PageHeader
        title="Data Extract"
        description="Condition and outcome tables for every curated test run, with provenance columns. Exports carry the filters and rubric version."
        actions={<ExportButtons request={request} />}
      />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[340px_minmax(0,1fr)]">
        <QueryBuilder />
        <div className="min-w-0 space-y-6">
          <ColumnPicker />
          <Card>
            <CardHeader title="Preview" description="First rows of the current query." />
            <PreviewTable request={request} />
          </Card>
        </div>
      </div>
    </>
  );
}
