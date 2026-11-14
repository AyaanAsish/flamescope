"use client";

import { FlowCanvas } from "@/components/architecture/FlowCanvas";
import { FlowViewer } from "@/components/architecture/FlowViewer";
import { StatusContext } from "@/components/architecture/NodeTypes";
import { useHydrated } from "@/components/ui/panel-state";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DIAGRAMS, type DiagramKey } from "@/content/architecture";
import { useStatus } from "@/lib/api/hooks";
import { useUrlState } from "@/lib/use-url-state";

const DIAGRAM_TABS: { value: DiagramKey; label: string }[] = [
  { value: "context", label: "System context" },
  { value: "layers", label: "Layers" },
  { value: "components", label: "Components" },
  { value: "dataflow", label: "Data flow" },
  { value: "datamodel", label: "Data model" },
];
const FLOWS_TAB = { value: "flows", label: "Call flows" } as const;
const DEPLOYMENT_TAB = { value: "deployment", label: "Deployment" } as const;
const TABS = [...DIAGRAM_TABS, FLOWS_TAB, DEPLOYMENT_TAB];
const DEFAULT_TAB = "context";
const DEFAULT_FLOW = "CF-01";

function useStatusMap(): Record<string, string> {
  const status = useStatus();
  const isHydrated = useHydrated();
  return Object.fromEntries(
    ((isHydrated && status.data?.components) || []).map((component) => [
      component.id,
      component.status,
    ]),
  );
}

export function ArchTabs({ flowSources }: { flowSources: Record<string, string> }) {
  const { params, patch } = useUrlState();
  const statuses = useStatusMap();
  const requested = params.get("tab");
  const active = TABS.some((tab) => tab.value === requested) ? (requested as string) : DEFAULT_TAB;
  const openFlow = (flowId: string) => patch({ tab: FLOWS_TAB.value, cf: flowId });
  const canvases: DiagramKey[] = [...DIAGRAM_TABS.map((tab) => tab.value), "deployment"];

  return (
    <StatusContext.Provider value={statuses}>
      <Tabs
        value={active}
        onValueChange={(value) => patch({ tab: value === DEFAULT_TAB ? null : value, cf: null })}
        data-testid="arch-tabs"
      >
        <TabsList aria-label="Architecture views">
          {TABS.map((tab) => (
            <TabsTrigger key={tab.value} value={tab.value}>
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>
        {canvases.map((key) => (
          <TabsContent key={key} value={key}>
            <FlowCanvas diagram={DIAGRAMS[key]} statuses={statuses} onOpenFlow={openFlow} />
          </TabsContent>
        ))}
        <TabsContent value={FLOWS_TAB.value}>
          <FlowViewer
            activeId={params.get("cf") ?? DEFAULT_FLOW}
            sources={flowSources}
            onSelect={(cf) => patch({ cf })}
          />
        </TabsContent>
      </Tabs>
    </StatusContext.Provider>
  );
}
