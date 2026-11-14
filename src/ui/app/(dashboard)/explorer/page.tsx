import type { Metadata } from "next";
import { ExplorerView } from "../_components/explorer-view";

export const metadata: Metadata = { title: "Explorer" };

export default function ExplorerPage() {
  return <ExplorerView />;
}
