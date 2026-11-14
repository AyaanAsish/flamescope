import { readFileSync } from "node:fs";
import path from "node:path";
import { FLOW_FILES } from "./index";

const FLOWS_DIR = path.join(process.cwd(), "content", "architecture", "flows");

/** Server-side loader: Mermaid sources keyed by flow ID (for example "CF-01"). */
export function loadFlowSources(): Record<string, string> {
  return Object.fromEntries(
    FLOW_FILES.map((file) => [
      file.replace(".mmd", "").toUpperCase(),
      readFileSync(path.join(FLOWS_DIR, file), "utf-8"),
    ]),
  );
}
