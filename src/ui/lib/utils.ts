import { clsx, type ClassValue } from "clsx";
import { extendTailwindMerge } from "tailwind-merge";

// `text-caption` is a font size (tailwind.config.ts); without this, tailwind-merge reads it as a
// text colour and drops the colour class it is combined with (for example `text-accent-fg`).
const twMerge = extendTailwindMerge({
  extend: { classGroups: { "font-size": [{ text: ["caption"] }] } },
});

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export function humanize(identifier: string): string {
  const spaced = identifier.replaceAll("_", " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}
