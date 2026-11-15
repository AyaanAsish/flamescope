import type { FuelPhase, Lens, RankLens } from "@/lib/api/types";

export const API_BASE_PATH = "/api/v1";

export const SCORE_DISCLAIMER = "Scores are relative decision aids, not safety certifications.";
export const DATA_CREDIT = "Data: NASA Physical Sciences Informatics (PSI)";
export const PSI_URL =
  "https://psi.nasa.gov/physci/repo/search?q=&data_source=psi&data_type=investigation";

export const STALE_TIME_CATALOG_MS = 5 * 60 * 1000;
export const STATUS_POLL_MS = 10_000;
export const SLIDER_DEBOUNCE_MS = 250;
// The doc 05 section 8 preview maximum, so the scatter plots every run (doc 09 CF-11).
export const OVERVIEW_SCATTER_LIMIT = 5000;
export const OVERVIEW_TOP_LIMIT = 5;
export const COMPARE_MIN = 2;
export const COMPARE_MAX = 4;
export const EXPLORER_PAGE_SIZE = 24;

export const LUNAR_ENVELOPE = { o2MinFraction: 0.3, pressureMaxKpa: 70.3 } as const;

export const LENSES: readonly Lens[] = ["habitat", "modeling", "controls"];
export const RANK_LENSES: readonly RankLens[] = ["overall", "habitat", "modeling", "controls"];

export const LENS_LABELS: Record<RankLens, string> = {
  overall: "Overall",
  habitat: "Habitat",
  modeling: "Modeling",
  controls: "Controls",
};

export const LENS_COLORS: Record<Lens, string> = {
  habitat: "var(--lens-habitat)",
  modeling: "var(--lens-modeling)",
  controls: "var(--lens-controls)",
};

export const PHASE_COLORS: Record<FuelPhase, string> = {
  gas: "var(--gas)",
  liquid: "var(--liquid)",
  solid: "var(--solid)",
};

export const PHASE_LABELS: Record<FuelPhase, string> = {
  gas: "Gas",
  liquid: "Liquid",
  solid: "Solid",
};
export const FUEL_PHASES: readonly FuelPhase[] = ["gas", "liquid", "solid"];

export const SORT_OPTIONS = [
  { value: "acronym", label: "Acronym" },
  { value: "overall", label: "Overall score" },
  { value: "habitat", label: "Habitat score" },
  { value: "modeling", label: "Modeling score" },
  { value: "controls", label: "Controls score" },
] as const;

export const SUGGESTED_QUESTIONS = [
  "Which experiments tested solids above 30% oxygen?",
  "What do the investigations say about flame spread at low flow speeds?",
  "Which hardware is shared between investigations?",
  "What is known about smoke detection in microgravity?",
];

export const EARTH_SECTORS = [
  "firefighting",
  "detection",
  "building_safety",
  "industrial",
  "wildfire",
  "transport",
] as const;

export const NAV_ITEMS = [
  { href: "/", label: "Overview", icon: "overview" },
  { href: "/explorer", label: "Explorer", icon: "explorer" },
  { href: "/ranking", label: "Ranking", icon: "ranking" },
  { href: "/compare", label: "Compare", icon: "compare" },
  { href: "/scenario", label: "Scenario Lab", icon: "scenario" },
  { href: "/extract", label: "Data Extract", icon: "extract" },
  { href: "/safety-tech", label: "Safety Tech", icon: "safety" },
  { href: "/earth", label: "Earth Apps", icon: "earth" },
  { href: "/ask", label: "Ask", icon: "ask" },
  { href: "/architecture", label: "Architecture", icon: "architecture" },
] as const;

export type NavIcon = (typeof NAV_ITEMS)[number]["icon"];
