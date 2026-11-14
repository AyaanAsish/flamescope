"use client";

import { Button } from "@/components/ui/button";

export default function GlobalError({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div
      role="alert"
      className="flex min-h-screen flex-col items-center justify-center gap-4 text-center"
    >
      <h1 className="text-2xl font-semibold">Something went wrong</h1>
      <p className="text-muted max-w-md text-sm">{error.message}</p>
      <Button variant="primary" onClick={reset}>
        Try again
      </Button>
    </div>
  );
}
