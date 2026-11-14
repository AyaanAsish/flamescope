"use client";

import { Download, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";
import { NarrativePanel } from "@/components/compare/NarrativePanel";
import { PageHeader } from "@/components/layout/PageHeader";
import { CoveragePanel } from "@/components/scenario/CoveragePanel";
import { GravityBoundingCard } from "@/components/scenario/GravityBoundingCard";
import { MatchList } from "@/components/scenario/MatchList";
import { ScenarioForm } from "@/components/scenario/ScenarioForm";
import {
  hasScenarioInput,
  readScenarioValues,
  type ScenarioValues,
  toScenarioRequest,
} from "@/components/scenario/scenario-values";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { DataPanel } from "@/components/ui/panel-state";
import { SkeletonRows } from "@/components/ui/skeleton";
import { useExtractExport, usePresets, useScenario } from "@/lib/api/hooks";
import type { ExportFormat, ScenarioResponse } from "@/lib/api/types";
import { SCORE_DISCLAIMER, SLIDER_DEBOUNCE_MS } from "@/lib/constants";
import type { PressureUnit } from "@/lib/format";
import { useDebouncedValue, useUrlState } from "@/lib/use-url-state";

const SCENARIO_KEYS = ["preset", "o2", "p", "g", "flow", "phase", "material", "unit"];

function ExportButtons({ scenarioId }: { scenarioId: string }) {
  const exporter = useExtractExport();
  const run = (format: ExportFormat) =>
    exporter.mutate({ filters: { scenario_id: scenarioId }, format });
  return (
    <div className="flex items-center gap-2">
      {(["csv", "json"] as const).map((format) => (
        <Button key={format} size="sm" disabled={exporter.isPending} onClick={() => run(format)}>
          <Download className="size-3.5" aria-hidden /> Export matching runs ({format.toUpperCase()}
          )
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

function ExplainSection({
  request,
  enabled,
  onExplain,
}: {
  request: ReturnType<typeof toScenarioRequest>;
  enabled: boolean;
  onExplain: () => void;
}) {
  const explained = useScenario({ ...request, explain: true }, enabled);
  const narrative = explained.isError
    ? { text: "", sentences: [], status: "unavailable" as const }
    : explained.data?.explanation;
  if (!enabled) {
    return (
      <Card>
        <CardHeader
          title="Interpretation"
          description="A cited written reading of these matches. Requires the language model."
          action={
            <Button variant="primary" size="sm" onClick={onExplain}>
              <Sparkles className="size-3.5" aria-hidden /> Explain
            </Button>
          }
        />
      </Card>
    );
  }
  return (
    <NarrativePanel
      title="Interpretation"
      narrative={narrative}
      isLoading={explained.isPending && !explained.isError}
    />
  );
}

function Results({
  data,
  unit,
  request,
}: {
  data: ScenarioResponse;
  unit: PressureUnit;
  request: ReturnType<typeof toScenarioRequest>;
}) {
  const [explainRequested, setExplainRequested] = useState(false);
  return (
    <div className="space-y-6">
      <CoveragePanel coverage={data.coverage} scenario={data.scenario} unit={unit} />
      <GravityBoundingCard bounding={data.gravity_bounding} />
      <ExplainSection
        request={request}
        enabled={explainRequested}
        onExplain={() => setExplainRequested(true)}
      />
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold">Closest matching investigations</h2>
        <ExportButtons scenarioId={data.scenario_id} />
      </div>
      {data.matches.length === 0 ? (
        <Card>
          <p className="text-muted py-6 text-center text-sm">
            No investigation has runs near this scenario.
          </p>
        </Card>
      ) : (
        <MatchList matches={data.matches} />
      )}
    </div>
  );
}

export function ScenarioView() {
  const { params, patch } = useUrlState();
  const presets = usePresets();
  const values = readScenarioValues(params);
  const unit: PressureUnit = params.get("unit") === "psi" ? "psi" : "kPa";
  // Debounce a string (stable identity) and enable on the settled values, so a request never
  // runs with values that lag the enabled check.
  const settledKey = useDebouncedValue(JSON.stringify(values), SLIDER_DEBOUNCE_MS);
  const settled = useMemo(() => JSON.parse(settledKey) as ScenarioValues, [settledKey]);
  const request = toScenarioRequest(settled, false);
  const scenario = useScenario(request, hasScenarioInput(settled));
  const reset = () => patch(Object.fromEntries(SCENARIO_KEYS.map((key) => [key, null])));

  return (
    <>
      <PageHeader
        title="Scenario Lab"
        description="Describe a habitat atmosphere and see which investigations come closest, where the catalog does not reach, and how gravity bounds the answer."
      />
      <p className="rounded-control border-line bg-surface1 text-caption text-muted mb-4 border px-4 py-2">
        {SCORE_DISCLAIMER} Similarity measures closeness of test conditions, not safety.
      </p>
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[360px_minmax(0,1fr)]">
        <ScenarioForm
          values={values}
          presets={presets.data}
          unit={unit}
          onChange={patch}
          onReset={reset}
        />
        {hasScenarioInput(values) ? (
          <DataPanel query={scenario} skeleton={<SkeletonRows rows={8} />}>
            {(data) => <Results data={data} unit={unit} request={request} />}
          </DataPanel>
        ) : (
          <Card>
            <p className="text-muted py-12 text-center text-sm">
              Choose a preset or set a value to match against the catalog.
            </p>
          </Card>
        )}
      </div>
    </>
  );
}
