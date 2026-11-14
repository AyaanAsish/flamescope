import type { Metadata } from "next";
import { EarthView } from "../_components/earth-view";

export const metadata: Metadata = { title: "Earth Apps" };

export default function EarthPage() {
  return <EarthView />;
}
