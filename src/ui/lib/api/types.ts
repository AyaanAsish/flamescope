/** Mirrors flamescope_common.schemas.api and schemas.card (docs 04 and 05). */

export type Json = string | number | boolean | null | Json[] | { [key: string]: Json };

export type Lens = "habitat" | "modeling" | "controls";
export type RankLens = Lens | "overall";
export type SortKey = "acronym" | "overall" | "habitat" | "modeling" | "controls";
export type FuelPhase = "gas" | "liquid" | "solid";
export type GravityLevel = "microgravity" | "normal" | "partial" | "mixed";
export type CoverageState = "covered" | "extrapolated" | "no_data";
export type NarrativeStatus = "ok" | "unavailable" | "skipped";
export type ExportFormat = "csv" | "json";
export type RangePair = [number, number];
/** A null end is open on that side (doc 04 s2, doc 05 s4), never a guessed bound. */
export type OpenRangePair = [number | null, number | null];
export type FindingCategory =
  | "detection"
  | "suppression"
  | "material_screening"
  | "post_fire"
  | "atmosphere_design"
  | "fundamental";
export type EarthSector =
  "firefighting" | "detection" | "building_safety" | "industrial" | "wildfire" | "transport";

export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export interface ErrorBody {
  code: string;
  message: string;
  details: Json;
  request_id: string | null;
}

export interface SourceRef {
  kind: "psi_page" | "document" | "publication" | "s3_object" | "curated";
  uri: string;
  title?: string | null;
  locator?: string | null;
  quote?: string | null;
  chunk_id?: number | null;
}

// --- health and meta ---------------------------------------------------------------------

export interface StatsResponse {
  investigations: number;
  test_runs: number;
  publications: number;
  findings: number;
  chunks: number;
  hardware: number;
  fuel_phase_counts: Record<string, number>;
  o2_range: OpenRangePair;
  pressure_range_kpa: OpenRangePair;
  rubric_version: string;
  last_ingest: string | null;
  ingest_mode: "seed" | "harvest" | null;
}

export interface ComponentStatus {
  id: string;
  status: string;
  detail?: string | null;
  provider?: string | null;
  model?: string | null;
  last_run?: Record<string, Json> | null;
}

export interface StatusResponse {
  components: ComponentStatus[];
}

export interface Criterion {
  id: string;
  label: string;
  weight: number;
  description: string;
  anchors: Record<string, string>;
}

export interface LensDefinition {
  label: string;
  description: string;
  criteria: Criterion[];
}

export interface RubricResponse {
  rubric_version: string;
  lens_weights: Record<Lens, number>;
  lenses: Record<Lens, LensDefinition>;
}

export interface RankingPreset {
  lens_weights: Record<Lens, number>;
  criterion_weights: Partial<Record<Lens, Record<string, number>>>;
}

export interface ScenarioPreset {
  o2_fraction: number;
  pressure_kpa: number;
  pressure_psi: number | null;
  gravity_g: number;
  flow_speed_cm_s: number;
  assumed_default: boolean;
  note: string;
}

export interface PresetsResponse {
  rubric_version: string | null;
  ranking: Record<string, RankingPreset>;
  scenario: Record<string, ScenarioPreset>;
  texts: { gravity_bounding: string };
}

// --- catalog -----------------------------------------------------------------------------

export interface InvestigationFilters {
  q?: string;
  fuel_phase?: FuelPhase[];
  material?: string;
  hardware?: string[];
  project?: string;
  tag?: string[];
  o2_min?: number;
  o2_max?: number;
  pressure_min_kpa?: number;
  pressure_max_kpa?: number;
  gravity_level?: GravityLevel;
}

export interface InvestigationListParams extends InvestigationFilters {
  sort?: SortKey;
  page?: number;
  page_size?: number;
}

export interface ScoreSet {
  habitat: number | null;
  modeling: number | null;
  controls: number | null;
  overall: number | null;
}

export interface InvestigationSummary {
  id: number;
  acronym: string;
  title: string;
  project: string | null;
  platform: string | null;
  gravity_level: string | null;
  fuel_phases: string[];
  hardware: string[];
  summary: string | null;
  fire_safety_tags: string[];
  o2_range: OpenRangePair | null;
  pressure_range_kpa: OpenRangePair | null;
  flow_range_cm_s: OpenRangePair | null;
  scores: ScoreSet;
  reviewed: boolean;
  psi_url: string | null;
}

export interface BreakdownItem {
  criterion: string;
  label: string;
  value: number | null;
  weight: number;
  contribution: number;
  rationale: string;
  evidence: SourceRef[];
  origin: "llm" | "seed" | "override";
}

export interface LensScore {
  score: number | null;
  confidence: number;
  breakdown: BreakdownItem[];
}

export interface PublicationOut {
  doi: string | null;
  title: string;
  authors: string[];
  year: number | null;
  venue: string | null;
  url: string | null;
  key_findings: Json;
}

export interface MeasurementOut {
  instrument: string;
  quantity: string;
  units: string | null;
  file_pattern: string | null;
  notes: string;
  source: SourceRef | null;
}

export interface FindingOut {
  id: number;
  statement: string;
  category: FindingCategory;
  source: SourceRef;
  confidence: number;
}

export interface ValueRange {
  min: number | null;
  max: number | null;
  source?: SourceRef | null;
}

export interface InvestigationCard {
  schema_version: number;
  acronym: string;
  title: string;
  project: string | null;
  platform: string | null;
  gravity_level: string | null;
  hardware: { name: string; role: string }[];
  objectives: { text: string; source: SourceRef }[];
  approach: { text: string; source: SourceRef } | null;
  fuels: {
    name: string;
    phase: FuelPhase;
    material_class: string | null;
    geometry: { shape: string | null; dimensions_mm: Record<string, number | null> } | null;
    source: SourceRef;
  }[];
  conditions: {
    o2_fraction: ValueRange | null;
    pressure_kpa: ValueRange | null;
    flow_speed_cm_s: ValueRange | null;
    flow_direction: string[];
    gravity_g: number[];
  } | null;
  variables: { varied: string[]; fixed: string[] };
  fire_safety_tags: string[];
  open_questions: string[];
  field_confidence: Record<string, number>;
}

export interface CardData {
  s3_prefix: string | null;
  volume_bytes: number | null;
  file_types: string[];
}

export interface InvestigationDetail extends InvestigationSummary {
  card: InvestigationCard;
  publications: PublicationOut[];
  measurements: MeasurementOut[];
  findings: FindingOut[];
  score_breakdown: Partial<Record<Lens, LensScore>>;
  run_count: number;
  data: CardData;
}

export interface RunCondition {
  o2_fraction: number | null;
  diluent: string | null;
  pressure_kpa: number | null;
  flow_speed_cm_s: number | null;
  flow_direction: string | null;
  gravity_g: number | null;
  e_field_kv: number | null;
  temperature_k: number | null;
}

export interface RunOutcome {
  ignited: boolean | null;
  flame_spread_rate_mm_s: number | null;
  burn_rate: number | null;
  extinction: boolean | null;
  smoke_point: number | null;
  cool_flame: boolean | null;
  notes: string | null;
}

export interface RunItem {
  id: number;
  label: string;
  fuel: { name: string; phase: FuelPhase } | null;
  geometry: Record<string, Json>;
  condition: RunCondition;
  outcome: RunOutcome;
  is_aggregate: boolean;
  source: SourceRef | null;
  confidence: number;
}

export interface VariablesResponse {
  varied: { name: string; values: Json[]; unit: string | null }[];
  fixed: { name: string; value: Json; unit: string | null }[];
  run_count: number;
}

export interface FacetValue {
  value: string;
  count: number;
}

export interface FacetsResponse {
  fuel_phase: FacetValue[];
  hardware: FacetValue[];
  project: FacetValue[];
  tag: FacetValue[];
  platform: FacetValue[];
  gravity_level: FacetValue[];
}

export interface LineageNode {
  id: string;
  type: "hardware" | "investigation" | "project";
  label: string;
  kind: string | null;
}

export interface LineageEdge {
  source: string;
  target: string;
  role: string;
}

export interface LineageGraph {
  nodes: LineageNode[];
  edges: LineageEdge[];
}

export interface ProjectOut {
  name: string;
  description: string | null;
  investigations: string[];
}

// --- ranking -----------------------------------------------------------------------------

export type CriterionWeights = Partial<Record<Lens, Record<string, number>>>;
export type LensWeights = Partial<Record<Lens, number>>;

export interface RankRequest {
  lens: RankLens;
  preset?: string;
  criterion_weights?: CriterionWeights;
  lens_weights?: LensWeights;
  filters?: InvestigationFilters;
  limit?: number;
}

export interface RankItem {
  rank: number;
  acronym: string;
  title: string;
  score: number | null;
  confidence: number | null;
  lens_scores: Partial<Record<Lens, number | null>>;
  breakdown: BreakdownItem[];
}

export interface RankResponse {
  lens: RankLens;
  rubric_version: string;
  weights_used: {
    lens_weights: Record<Lens, number>;
    criterion_weights: Record<Lens, Record<string, number>>;
  };
  items: RankItem[];
  disclaimer: string;
}

// --- compare -----------------------------------------------------------------------------

export interface CompareRequest {
  investigations: string[];
  narrative: boolean;
}

export interface MatrixRow {
  attribute: string;
  label: string;
  group: string;
  values: Record<string, Json>;
  same: boolean;
}

export interface NarrativeSentence {
  text: string;
  citations: SourceRef[];
}

export interface Narrative {
  text: string;
  sentences: NarrativeSentence[];
  status: NarrativeStatus;
}

export interface CompareResponse {
  investigations: InvestigationSummary[];
  matrix: MatrixRow[];
  shared: { hardware: string[]; tags: string[]; instruments: string[] };
  narrative: Narrative;
}

// --- scenario ----------------------------------------------------------------------------

export interface ScenarioWeights {
  o2: number;
  pressure: number;
  flow: number;
  fuel: number;
}

export interface ScenarioRequest {
  preset?: string;
  o2_fraction?: number;
  pressure_kpa?: number;
  gravity_g?: number;
  flow_speed_cm_s?: number;
  fuel_phase?: FuelPhase;
  material?: string;
  weights?: ScenarioWeights;
  explain: boolean;
  limit?: number;
}

export interface ResolvedScenario {
  preset: string | null;
  o2_fraction: number | null;
  pressure_kpa: number | null;
  gravity_g: number | null;
  flow_speed_cm_s: number | null;
  fuel_phase: FuelPhase | null;
  material: string | null;
  weights: ScenarioWeights;
  assumed_default: boolean;
}

export interface CoverageEntry {
  state: CoverageState;
  catalog_range: RangePair | null;
  catalog_values: number[] | null;
}

export interface ScenarioMatch {
  acronym: string;
  similarity: number;
  best_run: RunItem | null;
  median_similarity: number;
  per_dimension: Record<string, number>;
  matching_runs: number;
}

export interface GravityBound {
  gravity_g: number;
  investigations: string[];
}

export interface GravityBounding {
  partial_gravity_data: boolean;
  lower_bound: GravityBound | null;
  upper_bound: GravityBound | null;
  analogue: { acronym: string; note: string } | null;
  statement: string | null;
}

export interface ScenarioResponse {
  scenario: ResolvedScenario;
  coverage: Record<string, CoverageEntry>;
  matches: ScenarioMatch[];
  gravity_bounding: GravityBounding;
  explanation: Narrative;
  scenario_id: string;
}

// --- extract -----------------------------------------------------------------------------

export interface ExtractFilters {
  investigations?: string[];
  fuel_phase?: FuelPhase[];
  o2_min?: number;
  o2_max?: number;
  pressure_min_kpa?: number;
  pressure_max_kpa?: number;
  has_outcome?: string[];
  scenario_id?: string | null;
}

export interface ExtractRequest {
  filters: ExtractFilters;
  columns?: string[];
  limit?: number;
}

export interface ExportRequest extends ExtractRequest {
  format: ExportFormat;
}

export interface ColumnInfo {
  name: string;
  label: string;
  unit: string | null;
  description: string;
}

export interface Table {
  columns: ColumnInfo[];
  rows: Json[][];
  total: number;
}

export interface DictionaryResponse {
  columns: ColumnInfo[];
}

// --- insights and Earth applications -----------------------------------------------------

export interface SafetyFinding {
  id: number;
  statement: string;
  investigation: string;
  source: SourceRef;
  confidence: number;
}

export interface SafetyGroup {
  category: FindingCategory;
  label: string;
  findings: SafetyFinding[];
  investigations: string[];
}

export interface SafetyTechResponse {
  groups: SafetyGroup[];
}

export interface GapItem {
  id: string;
  title: string;
  detail: string;
  related: string[];
  future: string[];
}

export interface GapsResponse {
  gaps: GapItem[];
}

export interface EarthApplicationOut {
  id: number;
  title: string;
  sector: EarthSector;
  description: string;
  maturity: string | null;
  investigations: string[];
  findings: number[];
  references: SourceRef[];
}

export interface EarthApplicationsResponse {
  items: EarthApplicationOut[];
}

// --- ask (SSE) ---------------------------------------------------------------------------

export interface AskRequest {
  question: string;
  filters: { investigations: string[] };
  top_k?: number;
}

export interface RetrievedChunk {
  chunk_id: number;
  acronym: string;
  doc_title: string;
  score: number;
}

export interface AskMeta {
  request_id: string | null;
  retrieved: RetrievedChunk[];
}

export interface VerifiedSentence {
  text: string;
  citations: SourceRef[];
  supported: boolean;
}

export interface AskCitations {
  sentences: VerifiedSentence[];
  dropped: number;
}

export interface AskError {
  code: string;
  message: string;
}

export interface AskHandlers {
  onMeta?: (meta: AskMeta) => void;
  onToken?: (text: string) => void;
  onCitations?: (citations: AskCitations) => void;
  onRelated?: (investigations: string[]) => void;
  onDone?: () => void;
  onError?: (error: AskError) => void;
}
