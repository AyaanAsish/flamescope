import type { Metadata } from "next";
import { SafetyTechView } from "../_components/safety-tech-view";

export const metadata: Metadata = { title: "Safety Tech" };

export default function SafetyTechPage() {
  return <SafetyTechView />;
}
