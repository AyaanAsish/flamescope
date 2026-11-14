"use client";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Checkbox, FieldLabel, Input, Select } from "@/components/ui/input";
import { NumberField } from "@/components/ui/number-field";
import { Skeleton } from "@/components/ui/skeleton";
import { useFacets } from "@/lib/api/hooks";
import type { FacetValue, FacetsResponse } from "@/lib/api/types";
import { formatLabel } from "@/lib/format";
import { parseList, useUrlState } from "@/lib/use-url-state";

function FacetGroup({
  title,
  values,
  selected,
  onToggle,
}: {
  title: string;
  values: FacetValue[];
  selected: string[];
  onToggle: (value: string) => void;
}) {
  if (values.length === 0) return null;
  return (
    <fieldset>
      <legend className="text-muted mb-1 text-xs font-medium tracking-wide uppercase">
        {title}
      </legend>
      <div className="max-h-44 overflow-y-auto pr-1">
        {values.map((facet) => (
          <Checkbox
            key={facet.value}
            label={formatLabel(facet.value)}
            count={facet.count}
            checked={selected.includes(facet.value)}
            onChange={() => onToggle(facet.value)}
          />
        ))}
      </div>
    </fieldset>
  );
}

function FacetSelect({
  title,
  values,
  current,
  onChange,
}: {
  title: string;
  values: FacetValue[];
  current: string;
  onChange: (value: string) => void;
}) {
  const id = `facet-${title}`;
  return (
    <div>
      <FieldLabel htmlFor={id}>{title}</FieldLabel>
      <Select id={id} value={current} onChange={(event) => onChange(event.target.value)}>
        <option value="">Any</option>
        {values.map((facet) => (
          <option key={facet.value} value={facet.value}>
            {formatLabel(facet.value)} ({facet.count})
          </option>
        ))}
      </Select>
    </div>
  );
}

function numberParam(raw: string | null): number | undefined {
  return raw === null || raw === "" ? undefined : Number(raw);
}

function RangeFields({ facetsKey }: { facetsKey: string }) {
  const { params, patch } = useUrlState();
  const field = (key: string, label: string, unit: string, step: number) => (
    <NumberField
      key={`${facetsKey}-${key}`}
      label={label}
      unit={unit}
      step={step}
      min={0}
      value={numberParam(params.get(key))}
      onCommit={(value) => patch({ [key]: value, page: null })}
    />
  );
  return (
    <div className="grid grid-cols-2 gap-3">
      {field("o2_min", "O2 min", "%", 1)}
      {field("o2_max", "O2 max", "%", 1)}
      {field("pressure_min_kpa", "Pressure min", "kPa", 1)}
      {field("pressure_max_kpa", "Pressure max", "kPa", 1)}
    </div>
  );
}

function FilterBody({ facets }: { facets: FacetsResponse }) {
  const { params, patch } = useUrlState();
  const toggleIn = (key: string, value: string) => {
    const current = parseList(params.get(key));
    const next = current.includes(value)
      ? current.filter((item) => item !== value)
      : [...current, value];
    patch({ [key]: next.join(","), page: null });
  };
  return (
    <div className="space-y-5">
      <div>
        <FieldLabel htmlFor="explorer-q">Search</FieldLabel>
        <Input
          id="explorer-q"
          data-testid="explorer-q"
          defaultValue={params.get("q") ?? ""}
          key={params.get("q") ?? ""}
          placeholder="Title, summary, objective"
          onKeyDown={(event) =>
            event.key === "Enter" && patch({ q: event.currentTarget.value, page: null })
          }
          onBlur={(event) => patch({ q: event.target.value, page: null })}
        />
      </div>
      <FacetGroup
        title="Fuel phase"
        values={facets.fuel_phase}
        selected={parseList(params.get("fuel_phase"))}
        onToggle={(value) => toggleIn("fuel_phase", value)}
      />
      <FacetSelect
        title="Gravity"
        values={facets.gravity_level}
        current={params.get("gravity_level") ?? ""}
        onChange={(value) => patch({ gravity_level: value, page: null })}
      />
      <FacetSelect
        title="Project"
        values={facets.project}
        current={params.get("project") ?? ""}
        onChange={(value) => patch({ project: value, page: null })}
      />
      <RangeFields facetsKey={params.toString()} />
      <FacetGroup
        title="Hardware"
        values={facets.hardware}
        selected={parseList(params.get("hardware"))}
        onToggle={(value) => toggleIn("hardware", value)}
      />
      <FacetGroup
        title="Phenomena"
        values={facets.tag}
        selected={parseList(params.get("tag"))}
        onToggle={(value) => toggleIn("tag", value)}
      />
    </div>
  );
}

export function ExplorerFilters() {
  const facets = useFacets();
  const { params, patch } = useUrlState();
  const hasFilters = Array.from(params.keys()).some((key) => key !== "sort");
  return (
    <Card data-testid="explorer-filters" className="sticky top-0 space-y-4 self-start">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">Filters</h2>
        {hasFilters ? (
          <Button
            size="sm"
            variant="ghost"
            onClick={() =>
              patch(
                Object.fromEntries(
                  Array.from(params.keys())
                    .filter((key) => key !== "sort")
                    .map((key) => [key, null]),
                ),
              )
            }
          >
            Clear
          </Button>
        ) : null}
      </div>
      {facets.data ? (
        <FilterBody facets={facets.data} />
      ) : facets.isError ? (
        <div role="alert" className="text-muted space-y-2 text-sm">
          <p>Filters could not be loaded.</p>
          <Button size="sm" onClick={() => void facets.refetch()}>
            Retry
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          {Array.from({ length: 6 }, (_, index) => (
            <Skeleton key={index} className="h-8" />
          ))}
        </div>
      )}
    </Card>
  );
}
