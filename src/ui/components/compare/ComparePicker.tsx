"use client";

import { X } from "lucide-react";
import { Card } from "@/components/ui/card";
import { FieldLabel, Select } from "@/components/ui/input";
import { useInvestigations } from "@/lib/api/hooks";
import { COMPARE_MAX, COMPARE_MIN } from "@/lib/constants";

const PICKER_PAGE_SIZE = 100;

interface ComparePickerProps {
  selected: string[];
  onChange: (acronyms: string[]) => void;
}

export function ComparePicker({ selected, onChange }: ComparePickerProps) {
  const catalog = useInvestigations({ sort: "acronym", page_size: PICKER_PAGE_SIZE });
  const options = (catalog.data?.items ?? []).filter((item) => !selected.includes(item.acronym));
  const isFull = selected.length >= COMPARE_MAX;
  return (
    <Card data-testid="compare-picker" className="space-y-3">
      <div className="flex flex-wrap items-end gap-4">
        <div className="w-72">
          <FieldLabel htmlFor="compare-add">Add investigation</FieldLabel>
          <Select
            id="compare-add"
            data-testid="compare-add"
            value=""
            disabled={isFull || catalog.isPending}
            onChange={(event) => event.target.value && onChange([...selected, event.target.value])}
          >
            <option value="">{isFull ? `Maximum of ${COMPARE_MAX} reached` : "Choose..."}</option>
            {options.map((item) => (
              <option key={item.id} value={item.acronym}>
                {item.acronym} - {item.title}
              </option>
            ))}
          </Select>
        </div>
        <ul className="flex flex-wrap gap-2" aria-label="Selected investigations">
          {selected.map((acronym) => (
            <li
              key={acronym}
              className="rounded-control border-line-strong bg-surface2 flex items-center gap-1 border py-1 pr-1 pl-3 text-sm font-medium"
            >
              {acronym}
              <button
                type="button"
                aria-label={`Remove ${acronym}`}
                className="text-muted hover:bg-surface1 hover:text-fg rounded p-1"
                onClick={() => onChange(selected.filter((item) => item !== acronym))}
              >
                <X className="size-3.5" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      </div>
      <p className="text-caption text-muted">
        Select {COMPARE_MIN} to {COMPARE_MAX} investigations. {selected.length} selected.
      </p>
    </Card>
  );
}
