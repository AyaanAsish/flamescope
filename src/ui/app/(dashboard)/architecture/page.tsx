import type { Metadata } from "next";
import { ArchTabs } from "@/components/architecture/ArchTabs";
import { PageHeader } from "@/components/layout/PageHeader";
import { loadFlowSources } from "@/content/architecture/load-flows";

export const metadata: Metadata = { title: "Architecture" };

export default function ArchitecturePage() {
  return (
    <>
      <PageHeader
        title="Architecture"
        description="How FlameScope is built, rendered from the design documents. Component badges show live status from the running stack."
      />
      <ArchTabs flowSources={loadFlowSources()} />
    </>
  );
}
