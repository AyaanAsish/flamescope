"use client";

import { useId, useState } from "react";
import { FieldLabel, Input } from "@/components/ui/input";

interface NumberFieldProps {
  label: string;
  unit?: string;
  value: number | undefined;
  step?: number;
  min?: number;
  max?: number;
  onCommit: (value: number | undefined) => void;
  testId?: string;
}

/** Commits on blur or Enter so every keystroke does not refetch. */
export function NumberField({
  label,
  unit,
  value,
  step,
  min,
  max,
  onCommit,
  testId,
}: NumberFieldProps) {
  const id = useId();
  const [draft, setDraft] = useState(value === undefined ? "" : String(value));
  const [lastValue, setLastValue] = useState(value);
  if (value !== lastValue) {
    setLastValue(value);
    setDraft(value === undefined ? "" : String(value));
  }

  function commit() {
    const parsed = draft.trim() === "" ? undefined : Number(draft);
    onCommit(parsed !== undefined && Number.isFinite(parsed) ? parsed : undefined);
  }

  return (
    <div>
      <FieldLabel htmlFor={id}>{unit ? `${label} (${unit})` : label}</FieldLabel>
      <Input
        id={id}
        type="number"
        inputMode="decimal"
        value={draft}
        step={step}
        min={min}
        max={max}
        data-testid={testId}
        className="mono"
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => event.key === "Enter" && commit()}
      />
    </div>
  );
}
