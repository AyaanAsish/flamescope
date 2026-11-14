import components from "./components.json";
import context from "./context.json";
import dataflow from "./dataflow.json";
import datamodel from "./datamodel.json";
import deployment from "./deployment.json";
import layers from "./layers.json";
import type { ArchDiagram, FlowMeta } from "./types";

export type { ArchDiagram, FlowMeta } from "./types";

export const DIAGRAMS = {
  context: context as ArchDiagram,
  layers: layers as ArchDiagram,
  components: components as ArchDiagram,
  dataflow: dataflow as ArchDiagram,
  datamodel: datamodel as ArchDiagram,
  deployment: deployment as ArchDiagram,
};

export type DiagramKey = keyof typeof DIAGRAMS;

/** Sequence diagram files in `flows/`, one per call flow of document 09. */
export const FLOW_FILES = Array.from(
  { length: 13 },
  (_, index) => `cf-${String(index + 1).padStart(2, "0")}.mmd`,
);

const DOC = "09-call-flows.md";

export const FLOWS: FlowMeta[] = [
  {
    id: "CF-01",
    title: "Build and deploy bring-up",
    llm: "none",
    endpoints: ["GET /api/v1/ready", "GET /"],
    doc: `${DOC}#cf-01`,
    failure:
      "Any non-zero exit stops make deploy and prints a make logs hint. make undeploy runs compose down -v --remove-orphans.",
  },
  {
    id: "CF-02",
    title: "Seed ingestion of one investigation",
    llm: "optional",
    endpoints: [],
    doc: `${DOC}#cf-02`,
    failure:
      "Scores missing from the seed file are computed with the configured provider (ollama or mock). One investigation failing a stage is recorded in ingest_run and the pipeline continues with the others (document 06 section 6).",
  },
  {
    id: "CF-03",
    title: "Harvest ingestion of one investigation",
    llm: "yes",
    endpoints: [],
    doc: `${DOC}#cf-03`,
    failure:
      "An LLM schema failure after retries leaves the card as its previous version and is reported. S3 and network errors retry 3 times with backoff, then the investigation is marked and skipped (document 06 section 6). The review stage writes EarthAppsAgent output to earth_candidates.json only; candidates are published after curator review.",
  },
  {
    id: "CF-04",
    title: "Explorer: list and detail",
    llm: "none",
    endpoints: [
      "GET /investigations",
      "GET /facets",
      "GET /investigations/{id}",
      "GET /investigations/{id}/runs",
      "GET /investigations/{id}/variables",
    ],
    doc: `${DOC}#cf-04`,
    failure:
      "An unknown investigation returns 404 not_found in the error envelope (document 05 section 2); each panel shows its own error state with retry.",
  },
  {
    id: "CF-05",
    title: "Ranking",
    llm: "none",
    endpoints: ["POST /rank"],
    doc: `${DOC}#cf-05`,
    failure:
      "The UI debounces slider changes (250 ms) and keeps previous data while refetching. Ranking is deterministic for identical input and makes no LLM call.",
  },
  {
    id: "CF-06",
    title: "Compare",
    llm: "optional",
    endpoints: ["POST /compare"],
    doc: `${DOC}#cf-06`,
    failure:
      "An LLM error gives narrative.status = unavailable with HTTP 200; the UI shows the matrix and a muted notice.",
  },
  {
    id: "CF-07",
    title: "Scenario Lab",
    llm: "optional",
    endpoints: ["POST /scenario", "POST /extract/export"],
    doc: `${DOC}#cf-07`,
    failure:
      "An LLM error gives explanation.status = unavailable with HTTP 200; matches, coverage and gravity bounding are still returned. scenario_id is a stateless URL-safe base64 of the canonical scenario JSON, so export needs no server-side registry; a malformed id is 400 bad_request.",
  },
  {
    id: "CF-08",
    title: "Data extract",
    llm: "none",
    endpoints: ["GET /extract/dictionary", "POST /extract/preview", "POST /extract/export"],
    doc: `${DOC}#cf-08`,
    failure:
      "Invalid filters return 422 validation_error with field details; each panel shows its own error state with retry.",
  },
  {
    id: "CF-09",
    title: "Ask (cited question answering)",
    llm: "yes",
    endpoints: ["POST /ask (SSE)"],
    doc: `${DOC}#cf-09`,
    failure:
      "A gateway error after meta produces event: error and the UI keeps the retrieved sources visible. With no retrieval hits the fixed insufficient-information sentence is returned and no LLM is called.",
  },
  {
    id: "CF-10",
    title: "Safety Tech, gaps and Earth applications",
    llm: "none",
    endpoints: ["GET /insights/safety-tech", "GET /insights/gaps", "GET /earth-applications"],
    doc: `${DOC}#cf-10`,
    failure: "Each panel has its own loading, empty and error state with retry.",
  },
  {
    id: "CF-11",
    title: "Overview page",
    llm: "none",
    endpoints: ["GET /meta/stats", "POST /rank", "GET /insights/gaps", "POST /extract/preview"],
    doc: `${DOC}#cf-11`,
    failure:
      "The four requests run in parallel and each panel has its own loading and error state, so one failing request does not blank the page.",
  },
  {
    id: "CF-12",
    title: "Architecture page with live status",
    llm: "none",
    endpoints: ["GET /meta/status"],
    doc: `${DOC}#cf-12`,
    failure:
      "If /meta/status fails, diagrams still render from static JSON and node badges show an unknown state.",
  },
  {
    id: "CF-13",
    title: "Undeploy",
    llm: "none",
    endpoints: [],
    doc: `${DOC}#cf-13`,
    failure:
      "make undeploy removes containers, network and volumes; make clean additionally removes images and local caches.",
  },
];
