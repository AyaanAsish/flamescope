/** Response fixtures copied from the examples of doc 05 and the worked example of doc 08 section 6. */
import type {
  BreakdownItem,
  CompareResponse,
  DictionaryResponse,
  EarthApplicationsResponse,
  FacetsResponse,
  GapsResponse,
  GravityBounding,
  InvestigationDetail,
  InvestigationSummary,
  LineageGraph,
  Page,
  PresetsResponse,
  RankResponse,
  RubricResponse,
  RunItem,
  SafetyTechResponse,
  ScenarioResponse,
  SourceRef,
  StatsResponse,
  StatusResponse,
  Table,
  VariablesResponse,
} from "@/lib/api/types";

export const SOURCE: SourceRef = {
  kind: "psi_page",
  uri: "https://psi.nasa.gov/physci/repo/investigation/BASS-II",
  title: "BASS-II overview",
  locator: "Objectives",
  quote: "Flame spread over thin and thick solids.",
  chunk_id: 1,
};

/** Doc 05 section 4, `InvestigationSummary` example. */
export const BASS_II: InvestigationSummary = {
  id: 7,
  acronym: "BASS-II",
  title: "Burning and Suppression of Solids - II",
  project: null,
  platform: "ISS",
  gravity_level: "microgravity",
  fuel_phases: ["solid"],
  hardware: ["MSG", "SPICE flow duct"],
  summary: "Flame spread over solids in concurrent and opposed flow.",
  fire_safety_tags: ["flame_spread"],
  o2_range: [0.14, 0.21],
  pressure_range_kpa: [101.3, 101.3],
  flow_range_cm_s: [1, 55],
  scores: { habitat: 78.0, modeling: 64.0, controls: 51.0, overall: 66.0 },
  reviewed: true,
  psi_url: "https://psi.nasa.gov/physci/repo/investigation/BASS-II",
};

export const FLEX_2: InvestigationSummary = {
  ...BASS_II,
  id: 8,
  acronym: "FLEX-2",
  title: "Flame Extinguishment Experiment - 2",
  fuel_phases: ["liquid"],
  hardware: ["CIR", "MDCA"],
  reviewed: false,
};

/** Habitat lens of doc 08 section 1 and the worked example of section 6 (`flow_regime` null). */
const HABITAT_CRITERIA: [string, string, number, number | null][] = [
  ["fuel_realism", "Fuel realism", 0.25, 5],
  ["atmosphere_match", "Atmosphere match", 0.25, 3],
  ["flow_regime", "Flow regime", 0.15, null],
  ["phenomenon", "Phenomenon relevance", 0.2, 4],
  ["gravity_bounding", "Gravity bounding value", 0.15, 2],
];
const MAX_POINTS_PER_RATING = 20;
const scoredWeight = HABITAT_CRITERIA.reduce((sum, [, , w, v]) => sum + (v === null ? 0 : w), 0);

/** Contributions per doc 08 section 2: 20 * w_i * v_i / sum of scored weights. */
export const WORKED_BREAKDOWN: BreakdownItem[] = HABITAT_CRITERIA.map(([id, label, w, v]) => ({
  criterion: id,
  label,
  value: v,
  weight: w,
  contribution: v === null ? 0 : (MAX_POINTS_PER_RATING * w * v) / scoredWeight,
  rationale: `${label} rationale`,
  evidence: v === null ? [] : [SOURCE],
  origin: "seed",
}));

export const WORKED_SCORE = 72.94;
export const WORKED_CONFIDENCE = 0.85;

function criteria(rows: [string, string, number][]) {
  return rows.map(([id, label, weight]) => ({ id, label, weight, description: "", anchors: {} }));
}

/** Doc 08 section 1. */
export const RUBRIC: RubricResponse = {
  rubric_version: "2026.11-1",
  lens_weights: { habitat: 0.4, modeling: 0.3, controls: 0.3 },
  lenses: {
    habitat: {
      label: "Habitat relevance",
      description: "",
      criteria: criteria(HABITAT_CRITERIA.map(([id, label, w]) => [id, label, w])),
    },
    modeling: {
      label: "Value for predictive modeling",
      description: "",
      criteria: criteria([
        ["quantitative_outputs", "Quantitative outputs", 0.25],
        ["parameter_sweep", "Parameter sweep breadth", 0.25],
        ["geometry_definition", "Geometry and boundary definition", 0.15],
        ["data_accessibility", "Data accessibility", 0.2],
        ["model_validation", "Model and correlation support", 0.15],
      ]),
    },
    controls: {
      label: "Value for fire-safety controls",
      description: "",
      criteria: criteria([
        ["detection", "Detection", 0.25],
        ["suppression", "Suppression and extinction", 0.25],
        ["material_screening", "Material screening", 0.2],
        ["post_fire", "Post-fire and hidden hazards", 0.15],
        ["hardware_heritage", "Hardware and sensor heritage", 0.15],
      ]),
    },
  },
};

const DEFAULT_CRITERION_WEIGHTS = Object.fromEntries(
  Object.entries(RUBRIC.lenses).map(([lens, definition]) => [
    lens,
    Object.fromEntries(definition.criteria.map((item) => [item.id, item.weight])),
  ]),
) as RankResponse["weights_used"]["criterion_weights"];

/** Doc 05 section 3 and doc 08 sections 3 and 4.1. */
export const PRESETS: PresetsResponse = {
  rubric_version: "2026.11-1",
  ranking: {
    balanced: {
      lens_weights: { habitat: 0.4, modeling: 0.3, controls: 0.3 },
      criterion_weights: {},
    },
    lunar_habitat: {
      lens_weights: { habitat: 0.6, modeling: 0.2, controls: 0.2 },
      criterion_weights: {
        habitat: {
          atmosphere_match: 0.35,
          fuel_realism: 0.25,
          gravity_bounding: 0.2,
          phenomenon: 0.15,
          flow_regime: 0.05,
        },
      },
    },
  },
  scenario: {
    lunar_habitat: {
      o2_fraction: 0.34,
      pressure_kpa: 56.5,
      pressure_psi: 8.2,
      gravity_g: 0.166,
      flow_speed_cm_s: 10,
      assumed_default: true,
      note: "Within the challenge envelope; values are editable defaults.",
    },
    iss_cabin: {
      o2_fraction: 0.21,
      pressure_kpa: 101.3,
      pressure_psi: 14.7,
      gravity_g: 0,
      flow_speed_cm_s: 10,
      assumed_default: false,
      note: "Sea-level atmosphere in microgravity.",
    },
  },
  texts: { gravity_bounding: "The scenario gravity is {gravity_g} g." },
};

export const RANK: RankResponse = {
  lens: "habitat",
  rubric_version: "2026.11-1",
  weights_used: { lens_weights: RUBRIC.lens_weights, criterion_weights: DEFAULT_CRITERION_WEIGHTS },
  items: [
    {
      rank: 1,
      acronym: "BASS-II",
      title: BASS_II.title,
      score: WORKED_SCORE,
      confidence: WORKED_CONFIDENCE,
      lens_scores: { habitat: WORKED_SCORE, modeling: 64.0, controls: 51.0 },
      breakdown: WORKED_BREAKDOWN,
    },
  ],
  disclaimer: "Scores are relative decision aids, not safety certifications.",
};

export const STATS: StatsResponse = {
  investigations: 24,
  test_runs: 180,
  publications: 40,
  findings: 60,
  chunks: 900,
  hardware: 12,
  fuel_phase_counts: { gas: 8, liquid: 6, solid: 10 },
  o2_range: [0.1, 0.85],
  pressure_range_kpa: [50, 101.3],
  rubric_version: "2026.11-1",
  last_ingest: "2026-11-14T08:00:00Z",
  ingest_mode: "seed",
};

/** Doc 05 section 8 default columns used by the Overview scatter (CF-11). */
export const SCATTER_TABLE: Table = {
  columns: ["o2_fraction", "pressure_kpa", "fuel_phase", "investigation"].map((name) => ({
    name,
    label: name,
    unit: null,
    description: "",
  })),
  rows: [[0.21, 101.3, "solid", "BASS-II"]],
  total: 1,
};

export const PREVIEW_TABLE: Table = {
  columns: [
    { name: "investigation", label: "Investigation", unit: null, description: "" },
    { name: "o2_fraction", label: "Oxygen fraction", unit: "fraction", description: "" },
    { name: "pressure_kpa", label: "Pressure", unit: "kPa", description: "" },
  ],
  rows: [["BASS-II", 0.21, 101.3]],
  total: 1,
};

export const DICTIONARY: DictionaryResponse = { columns: PREVIEW_TABLE.columns };

/** Doc 05 section 9. */
export const GAPS: GapsResponse = {
  gaps: [
    {
      id: "partial_gravity",
      title: "No partial-gravity data",
      detail: "No run between 0 g and 1 g.",
      related: ["E-FIELD Flames"],
      future: ["LUCI", "FM2"],
    },
  ],
};

export const FACETS: FacetsResponse = {
  fuel_phase: [{ value: "solid", count: 6 }],
  hardware: [{ value: "MSG", count: 3 }],
  project: [],
  tag: [{ value: "flame_spread", count: 4 }],
  platform: [{ value: "ISS", count: 10 }],
  gravity_level: [{ value: "microgravity", count: 10 }],
};

export function pageOf<T>(items: T[]): Page<T> {
  return { items, page: 1, page_size: 24, total: items.length };
}

export const RUN: RunItem = {
  id: 1,
  label: "Run 1",
  fuel: { name: "PMMA", phase: "solid" },
  geometry: {},
  condition: {
    o2_fraction: 0.21,
    diluent: "N2",
    pressure_kpa: 101.3,
    flow_speed_cm_s: 20,
    flow_direction: "concurrent",
    gravity_g: 0,
    e_field_kv: null,
    temperature_k: null,
  },
  outcome: {
    ignited: true,
    flame_spread_rate_mm_s: 1.2,
    burn_rate: null,
    extinction: false,
    smoke_point: null,
    cool_flame: null,
    notes: null,
  },
  is_aggregate: false,
  source: SOURCE,
  confidence: 0.8,
};

export const VARIABLES: VariablesResponse = {
  varied: [{ name: "o2_fraction", values: [0.14, 0.17, 0.21], unit: "fraction" }],
  fixed: [{ name: "pressure_kpa", value: 101.3, unit: "kPa" }],
  run_count: 12,
};

export const DETAIL: InvestigationDetail = {
  ...BASS_II,
  card: {
    schema_version: 1,
    acronym: "BASS-II",
    title: BASS_II.title,
    project: null,
    platform: "ISS",
    gravity_level: "microgravity",
    hardware: [{ name: "MSG", role: "facility" }],
    objectives: [{ text: "Study flame spread over solids.", source: SOURCE }],
    approach: null,
    fuels: [],
    conditions: null,
    variables: { varied: ["o2_fraction"], fixed: ["pressure_kpa"] },
    fire_safety_tags: ["flame_spread"],
    open_questions: [],
    field_confidence: {},
  },
  publications: [],
  measurements: [],
  findings: [],
  score_breakdown: {
    habitat: { score: WORKED_SCORE, confidence: WORKED_CONFIDENCE, breakdown: WORKED_BREAKDOWN },
  },
  run_count: 12,
  data: { s3_prefix: null, volume_bytes: null, file_types: [] },
};

/** Doc 05 section 6; attribute order starts `project`, `platform`, `gravity_level`, `hardware`, `fuel_phase`. */
export const COMPARE: CompareResponse = {
  investigations: [BASS_II, FLEX_2],
  matrix: [
    {
      attribute: "platform",
      label: "Platform",
      group: "mission",
      values: { "BASS-II": "ISS", "FLEX-2": "ISS" },
      same: true,
    },
    {
      attribute: "fuel_phase",
      label: "Fuel phase",
      group: "fuel",
      values: { "BASS-II": ["solid"], "FLEX-2": ["liquid"] },
      same: false,
    },
    {
      attribute: "o2_range",
      label: "Oxygen range",
      group: "atmosphere",
      values: { "BASS-II": [0.14, 0.21], "FLEX-2": [0.14, 0.21] },
      same: true,
    },
  ],
  shared: { hardware: ["MSG"], tags: ["extinction"], instruments: [] },
  narrative: {
    text: "Both ran on the ISS.",
    sentences: [{ text: "Both ran on the ISS.", citations: [SOURCE] }],
    status: "ok",
  },
};

export const LINEAGE: LineageGraph = {
  nodes: [
    { id: "inv:BASS-II", type: "investigation", label: "BASS-II", kind: null },
    { id: "hw:MSG", type: "hardware", label: "MSG", kind: "facility" },
  ],
  edges: [{ source: "inv:BASS-II", target: "hw:MSG", role: "apparatus" }],
};

/** Doc 05 section 7 response example. */
export const GRAVITY_BOUNDING: GravityBounding = {
  partial_gravity_data: false,
  lower_bound: { gravity_g: 0, investigations: ["BASS-II"] },
  upper_bound: { gravity_g: 1, investigations: [] },
  analogue: { acronym: "E-FIELD Flames", note: "Electric fields change buoyancy-like flows." },
  statement: "No partial-gravity combustion data exists in PSI yet.",
};

export const SCENARIO: ScenarioResponse = {
  scenario: {
    preset: "lunar_habitat",
    o2_fraction: 0.34,
    pressure_kpa: 56.5,
    gravity_g: 0.166,
    flow_speed_cm_s: 10,
    fuel_phase: null,
    material: null,
    weights: { o2: 0.35, pressure: 0.25, flow: 0.15, fuel: 0.25 },
    assumed_default: true,
  },
  coverage: {
    o2_fraction: { state: "covered", catalog_range: [0.1, 0.85], catalog_values: null },
    pressure_kpa: { state: "extrapolated", catalog_range: [70, 101.3], catalog_values: null },
    flow_speed_cm_s: { state: "covered", catalog_range: [0, 60], catalog_values: null },
    gravity_g: { state: "no_data", catalog_range: null, catalog_values: [0, 1] },
  },
  matches: [
    {
      acronym: "BASS-II",
      similarity: 0.81,
      best_run: RUN,
      median_similarity: 0.62,
      per_dimension: { o2: 0.9, pressure: 0.4, flow: 0.95, fuel: 1.0 },
      matching_runs: 7,
    },
  ],
  gravity_bounding: GRAVITY_BOUNDING,
  explanation: { text: "", sentences: [], status: "skipped" },
  scenario_id: "eyJhc3N1bWVkX2RlZmF1bHQiOnRydWV9",
};

export const SAFETY_TECH: SafetyTechResponse = {
  groups: [
    {
      category: "detection",
      label: "Detection",
      findings: [
        {
          id: 1,
          statement: "Smoke particles are larger in microgravity.",
          investigation: "SAME",
          source: SOURCE,
          confidence: 0.8,
        },
      ],
      investigations: ["SAME"],
    },
  ],
};

export const EARTH: EarthApplicationsResponse = {
  items: [
    {
      id: 1,
      title: "Fine water mist extinguishers",
      sector: "firefighting",
      description: "Mist suppression informed by droplet combustion.",
      maturity: "deployed",
      investigations: ["FLEX-2"],
      findings: [],
      references: [SOURCE],
    },
  ],
};

export const STATUS: StatusResponse = {
  components: [
    { id: "C-API", status: "up", detail: "ok" },
    { id: "C-DB", status: "up" },
    { id: "C-LLM", status: "mock", provider: "mock", model: null },
    { id: "C-ING", status: "idle" },
  ],
};
