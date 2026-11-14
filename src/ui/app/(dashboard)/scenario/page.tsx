import type { Metadata } from "next";
import { ScenarioView } from "../_components/scenario-view";

export const metadata: Metadata = { title: "Scenario Lab" };

export default function ScenarioPage() {
  return <ScenarioView />;
}
