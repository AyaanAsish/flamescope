"use client";

import { FieldLabel, Select } from "@/components/ui/input";
import { usePresets } from "@/lib/api/hooks";
import { formatLabel } from "@/lib/format";

interface PresetSelectProps {
  preset: string;
  onPresetChange: (preset: string) => void;
}

export function PresetSelect({ preset, onPresetChange }: PresetSelectProps) {
  const presets = usePresets();
  const names = Object.keys(presets.data?.ranking ?? {});
  return (
    <div className="w-56">
      <FieldLabel htmlFor="ranking-preset">Preset</FieldLabel>
      <Select
        id="ranking-preset"
        data-testid="ranking-preset"
        value={preset}
        disabled={presets.isPending}
        onChange={(event) => onPresetChange(event.target.value)}
      >
        <option value="">Rubric defaults</option>
        {names.map((name) => (
          <option key={name} value={name}>
            {formatLabel(name)}
          </option>
        ))}
      </Select>
    </div>
  );
}
