"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface SheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  testId?: string;
  widthClass?: string;
  children: ReactNode;
}

/** Right-hand drawer; Esc and the close button dismiss it. */
export function Sheet({
  open,
  onOpenChange,
  title,
  description,
  testId,
  widthClass,
  children,
}: SheetProps) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="bg-bg/70 fixed inset-0 z-40" />
        <DialogPrimitive.Content
          data-testid={testId}
          className={cn(
            "slide-in border-line bg-surface1 fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col border-l",
            widthClass,
          )}
        >
          <div className="border-line flex items-start justify-between gap-4 border-b p-5">
            <div>
              <DialogPrimitive.Title className="text-base font-semibold">
                {title}
              </DialogPrimitive.Title>
              <DialogPrimitive.Description className="text-caption text-muted mt-0.5">
                {description ?? "Details"}
              </DialogPrimitive.Description>
            </div>
            <DialogPrimitive.Close
              aria-label="Close panel"
              className="rounded-control text-muted hover:bg-surface2 hover:text-fg p-1.5"
            >
              <X className="size-4" />
            </DialogPrimitive.Close>
          </div>
          <div className="flex-1 overflow-y-auto p-5">{children}</div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
