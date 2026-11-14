"use client";

import * as SliderPrimitive from "@radix-ui/react-slider";
import { cn } from "@/lib/utils";

interface SliderProps {
  value: number;
  min: number;
  max: number;
  step: number;
  label: string;
  onChange: (value: number) => void;
  className?: string;
}

export function Slider({ value, min, max, step, label, onChange, className }: SliderProps) {
  return (
    <SliderPrimitive.Root
      className={cn("relative flex h-5 w-full touch-none items-center select-none", className)}
      value={[value]}
      min={min}
      max={max}
      step={step}
      onValueChange={([next]) => onChange(next ?? value)}
    >
      <SliderPrimitive.Track className="bg-surface2 relative h-1.5 grow rounded-full">
        <SliderPrimitive.Range className="bg-accent absolute h-full rounded-full" />
      </SliderPrimitive.Track>
      <SliderPrimitive.Thumb
        aria-label={label}
        className="border-accent bg-surface1 block size-4 rounded-full border-2 transition-transform hover:scale-110"
      />
    </SliderPrimitive.Root>
  );
}
