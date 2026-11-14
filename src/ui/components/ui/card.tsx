import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-card border-line bg-surface1 border p-5 shadow-[0_1px_0_var(--inset-highlight)_inset]",
        className,
      )}
      {...props}
    />
  );
}

interface CardHeaderProps {
  title: string;
  description?: string;
  action?: ReactNode;
}

export function CardHeader({ title, description, action }: CardHeaderProps) {
  return (
    <div className="mb-4 flex items-start justify-between gap-4">
      <div>
        <h2 className="text-fg text-base font-semibold">{title}</h2>
        {description ? <p className="text-caption text-muted mt-0.5">{description}</p> : null}
      </div>
      {action}
    </div>
  );
}
