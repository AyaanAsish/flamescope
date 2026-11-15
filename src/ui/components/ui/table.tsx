import type { HTMLAttributes, TdHTMLAttributes, ThHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

interface TableProps extends HTMLAttributes<HTMLTableElement> {
  /** Names the scroll region for assistive technology; wide tables scroll sideways. */
  label?: string;
}

export function Table({ className, label = "Table", ...props }: TableProps) {
  return (
    // Focusable so keyboard users can scroll a wide table (WCAG 2.1.1, axe scrollable-region-focusable).
    <div
      className="rounded-card border-line relative overflow-x-auto border"
      tabIndex={0}
      role="region"
      aria-label={label}
    >
      <table className={cn("w-full border-collapse text-sm", className)} {...props} />
    </div>
  );
}

export function Th({ className, ...props }: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={cn(
        "border-line bg-surface2 text-muted border-b px-3 py-2.5 text-left text-xs font-medium tracking-wide whitespace-nowrap uppercase",
        className,
      )}
      {...props}
    />
  );
}

export function Td({ className, ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td
      className={cn("tabular border-line text-fg border-b px-3 py-2.5 align-top", className)}
      {...props}
    />
  );
}

export function Tr({ className, ...props }: HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr
      className={cn("hover:bg-surface2/60 transition-colors last:*:border-b-0", className)}
      {...props}
    />
  );
}
