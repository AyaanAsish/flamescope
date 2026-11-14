import type { Metadata } from "next";
import {
  OverviewGaps,
  OverviewHero,
  OverviewScatter,
  OverviewStats,
  OverviewTop,
  QuickLinks,
} from "./_components/overview-panels";

export const metadata: Metadata = { title: "Overview" };

export default function OverviewPage() {
  return (
    <div className="space-y-6">
      <OverviewHero />
      <OverviewStats />
      <OverviewScatter />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <OverviewTop />
        <OverviewGaps />
      </div>
      <QuickLinks />
    </div>
  );
}
