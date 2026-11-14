"use client";

import { useStats } from "@/lib/api/hooks";
import { DATA_CREDIT, SCORE_DISCLAIMER } from "@/lib/constants";

export function Footer() {
  const stats = useStats();
  return (
    <footer className="max-w-content border-line text-muted mx-auto mt-10 flex w-full flex-wrap items-center justify-between gap-x-6 gap-y-1 border-t px-6 py-4 text-xs">
      <span>{SCORE_DISCLAIMER}</span>
      <span className="mono">Rubric {stats.data?.rubric_version ?? "n/a"}</span>
      <span>{DATA_CREDIT}</span>
    </footer>
  );
}
