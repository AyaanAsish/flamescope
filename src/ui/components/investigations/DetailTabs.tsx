"use client";

import { RunsTable } from "@/components/investigations/RunsTable";
import { VariablesPanel } from "@/components/investigations/VariablesPanel";
import {
  DataFilesPanel,
  MeasurementsPanel,
  PublicationsPanel,
  ScoresPanel,
  SummaryPanel,
} from "@/components/investigations/DetailPanels";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { InvestigationDetail } from "@/lib/api/types";
import { useUrlState } from "@/lib/use-url-state";

const TABS = [
  { value: "summary", label: "Summary" },
  { value: "runs", label: "Test runs" },
  { value: "variables", label: "Variables" },
  { value: "measurements", label: "Measurements" },
  { value: "publications", label: "Publications" },
  { value: "scores", label: "Scores" },
  { value: "data", label: "Data" },
] as const;

const DEFAULT_TAB = "summary";

export function DetailTabs({ detail }: { detail: InvestigationDetail }) {
  const { params, patch } = useUrlState();
  const active = TABS.some((tab) => tab.value === params.get("tab"))
    ? params.get("tab")!
    : DEFAULT_TAB;
  const id = detail.acronym;
  return (
    <Tabs
      value={active}
      onValueChange={(value) => patch({ tab: value === DEFAULT_TAB ? null : value })}
      data-testid="detail-tabs"
    >
      <TabsList>
        {TABS.map((tab) => (
          <TabsTrigger key={tab.value} value={tab.value}>
            {tab.label}
          </TabsTrigger>
        ))}
      </TabsList>
      <TabsContent value="summary">
        <SummaryPanel detail={detail} />
      </TabsContent>
      <TabsContent value="runs">
        <RunsTable id={id} />
      </TabsContent>
      <TabsContent value="variables">
        <VariablesPanel id={id} />
      </TabsContent>
      <TabsContent value="measurements">
        <MeasurementsPanel detail={detail} />
      </TabsContent>
      <TabsContent value="publications">
        <PublicationsPanel id={id} />
      </TabsContent>
      <TabsContent value="scores">
        <ScoresPanel detail={detail} />
      </TabsContent>
      <TabsContent value="data">
        <DataFilesPanel detail={detail} />
      </TabsContent>
    </Tabs>
  );
}
