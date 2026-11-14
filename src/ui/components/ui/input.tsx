import type { InputHTMLAttributes, SelectHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const controlClass =
  "h-9 w-full rounded-control border border-line bg-surface2 px-3 text-sm text-fg placeholder:text-muted transition-colors hover:border-line-strong focus-visible:border-line-strong";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(controlClass, className)} {...props} />;
}

export function Select({ className, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className={cn(controlClass, "pr-8", className)} {...props} />;
}

interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label: string;
  count?: number;
}

export function Checkbox({ label, count, className, ...props }: CheckboxProps) {
  return (
    <label
      className={cn(
        "text-muted hover:text-fg flex cursor-pointer items-center gap-2 py-1 text-sm",
        className,
      )}
    >
      <input type="checkbox" className="size-4 accent-[var(--accent)]" {...props} />
      <span className="flex-1">{label}</span>
      {count === undefined ? null : <span className="mono text-muted text-xs">{count}</span>}
    </label>
  );
}

export function FieldLabel({ children, htmlFor }: { children: string; htmlFor?: string }) {
  return (
    <label
      htmlFor={htmlFor}
      className="text-muted mb-1 block text-xs font-medium tracking-wide uppercase"
    >
      {children}
    </label>
  );
}
