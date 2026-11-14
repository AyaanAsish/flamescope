import type { Metadata } from "next";
import { RankingView } from "../_components/ranking-view";

export const metadata: Metadata = { title: "Ranking" };

export default function RankingPage() {
  return <RankingView />;
}
