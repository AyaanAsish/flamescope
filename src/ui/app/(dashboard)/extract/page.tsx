import type { Metadata } from "next";
import { ExtractView } from "../_components/extract-view";

export const metadata: Metadata = { title: "Data Extract" };

export default function ExtractPage() {
  return <ExtractView />;
}
