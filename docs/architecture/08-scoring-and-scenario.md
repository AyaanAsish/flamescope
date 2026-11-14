# 08 - Relevance Scoring and Scenario Matching

## 1. Rubric

File: `src/data/rubric.yaml`. Version string: `rubric_version` (for example `2026.11-1`). Three lenses, five criteria each. Each criterion is rated 0 to 5 by the scorer agent (or a seed file or an override) with evidence; `null` when there is no evidence.

### Lens `habitat` - relevance to crewed-habitat fire safety (objective O1)

| Criterion ID | Label | Default weight | Rating anchors (0 / 3 / 5) |
|--------------|-------|----------------|----------------------------|
| `fuel_realism` | Fuel realism | 0.25 | gaseous fundamental flame / liquid or thin idealized solid / practical cabin materials or thick solids |
| `atmosphere_match` | Atmosphere match | 0.25 | air at 1 atm only / elevated oxygen or reduced pressure / covers 30%+ oxygen and reduced pressure |
| `flow_regime` | Flow regime | 0.15 | no flow control / single flow speed / low-speed ventilation-range sweep including quiescent |
| `phenomenon` | Phenomenon relevance | 0.20 | unrelated fundamental / related (soot, flame structure) / ignition, flame spread, flammability limit, extinction |
| `gravity_bounding` | Gravity bounding value | 0.15 | microgravity only without 1 g comparison / with 1 g comparison / explicit partial-gravity analogue or comparison |

### Lens `modeling` - value for predictive modeling (objective O2)

| Criterion ID | Label | Default weight | Rating anchors (0 / 3 / 5) |
|--------------|-------|----------------|----------------------------|
| `quantitative_outputs` | Quantitative outputs | 0.25 | qualitative only / some measured quantities / spread rates, limits, burn rates reported with conditions |
| `parameter_sweep` | Parameter sweep breadth | 0.25 | single condition / one parameter varied / several parameters varied systematically |
| `geometry_definition` | Geometry and boundary definition | 0.15 | unclear / partly specified / fully specified sample and flow geometry |
| `data_accessibility` | Data accessibility | 0.20 | video only / mixed / tabular data and documentation in PSI |
| `model_validation` | Model and correlation support | 0.15 | none / referenced / publications with validated models or correlations |

### Lens `controls` - value for fire-safety controls and equipment (objective O3)

| Criterion ID | Label | Default weight | Rating anchors (0 / 3 / 5) |
|--------------|-------|----------------|----------------------------|
| `detection` | Detection | 0.25 | none / indirect (soot, products) / smoke or aerosol characterization for detectors |
| `suppression` | Suppression and extinction | 0.25 | none / extinction limits observed / suppression agents or strategies tested |
| `material_screening` | Material screening | 0.20 | none / informs screening / directly supports flammability test methods |
| `post_fire` | Post-fire and hidden hazards | 0.15 | none / related / cool flames, re-ignition, toxic products, cleanup |
| `hardware_heritage` | Hardware and sensor heritage | 0.15 | one-off / reused apparatus / instruments reusable in future systems |

## 2. Formulas

For an investigation and a lens with criteria `i`, weights `w_i` (after overrides, normalized so they sum to 1) and values `v_i` in 0..5 or null:

```
N           = { i : v_i is not null }
lens_score  = 20 * ( sum_{i in N} w_i * v_i ) / ( sum_{i in N} w_i )        # 0..100; null if N is empty
confidence  = sum_{i in N} w_i                                              # 0..1
contribution_i = 20 * w_i * v_i / ( sum_{i in N} w_i )                      # for the breakdown bar

overall     = ( sum_{l in L} W_l * lens_score_l ) / ( sum_{l in L} W_l )    # L = lenses with non-null score
overall_confidence = sum_l W_l * confidence_l (W normalized)
```

Default lens weights `W`: habitat 0.4, modeling 0.3, controls 0.3.

Ordering: descending score, then descending confidence, then acronym. Investigations with a null score go last.

Rounding: scores to one decimal in responses; computation in float.

## 3. Ranking presets (`src/data/presets.yaml`, key `ranking`)

| Preset | Lens weights | Criterion emphasis |
|--------|--------------|--------------------|
| `balanced` | 0.4 / 0.3 / 0.3 | rubric defaults |
| `lunar_habitat` | 0.6 / 0.2 / 0.2 | `atmosphere_match` 0.35, `fuel_realism` 0.25, `gravity_bounding` 0.20, `phenomenon` 0.15, `flow_regime` 0.05 |
| `spacecraft_cabin` | 0.5 / 0.2 / 0.3 | `flow_regime` 0.25, `fuel_realism` 0.25, `phenomenon` 0.25, `atmosphere_match` 0.15, `gravity_bounding` 0.10 |
| `modeler` | 0.2 / 0.6 / 0.2 | rubric defaults within lenses |
| `equipment_designer` | 0.2 / 0.2 / 0.6 | `detection` 0.30, `suppression` 0.30, others scaled |

## 4. Scenario matching

### 4.1 Scenario presets (key `scenario`)

| Preset | O2 fraction | Pressure | Gravity | Flow | Note |
|--------|-------------|----------|---------|------|------|
| `lunar_habitat` | 0.34 | 56.5 kPa (8.2 psi) | 0.166 g | 10 cm/s | Within the challenge's "30% or greater, 10.2 psi or less" envelope; values are editable defaults. |
| `lunar_habitat_threshold` | 0.30 | 70.3 kPa (10.2 psi) | 0.166 g | 10 cm/s | The envelope boundary stated in the challenge. |
| `iss_cabin` | 0.21 | 101.3 kPa (14.7 psi) | 0 g | 10 cm/s | Sea-level atmosphere in microgravity. |
| `spacesuit` | 1.00 | 29.6 kPa (4.3 psi) | 0 g | 0 cm/s | From the challenge text. |
| `mars_habitat` | 0.34 | 56.5 kPa | 0.38 g | 10 cm/s | Same atmosphere assumption, Mars gravity. |

Preset atmospheres other than the challenge-stated numbers are design assumptions and must be labeled "assumed default" in the UI.

### 4.2 Distance

Catalog ranges `R_d = [min_d, max_d]` over all conditions with a value, for `d` in `o2_fraction`, `pressure_kpa`, `flow_speed_cm_s`.

```
num_d(s, c)  = min( 1, |s_d - c_d| / max(max_d - min_d, eps) )       # numeric dimensions
             = 1 if c_d is null                                     # missing data is the worst case
fuel(s, c)   = 0    if material matches (case-insensitive) 
             = 0.3  if same material_class
             = 0.6  if same phase only
             = 1    otherwise; 0 if the scenario gives no fuel
distance     = ( w_o2*num_o2 + w_p*num_p + w_f*num_flow + w_fuel*fuel ) / ( w_o2 + w_p + w_f + w_fuel )
similarity   = 1 - distance
```

Default weights: o2 0.35, pressure 0.25, flow 0.15, fuel 0.25. Dimensions the scenario leaves unset are removed from numerator and denominator.

For aggregate runs (ranges), `|s_d - c_d|` is 0 when `s_d` lies inside the run's range, otherwise the distance to the nearest endpoint.

Gravity is deliberately **not** part of the distance (ADR-08).

Investigation-level: `similarity = max over runs`, `median_similarity = median over runs`, `matching_runs = count with similarity >= 0.6`. Sort by `similarity`, then `median_similarity`.

### 4.3 Coverage

For each numeric dimension: `covered` if `min_d <= s_d <= max_d`; `extrapolated` if outside; `no_data` if the catalog has no values. Gravity: `covered` only if a run exists with `|gravity_g - s_g| <= 0.02`; otherwise `no_data`.

### 4.4 Gravity bounding

```
if scenario.gravity_g in catalog gravity values:   partial_gravity_data = (0 < g < 1)
else:
    lower_bound = investigations among the top matches with runs at 0 g
    upper_bound = investigations among the top matches with runs at 1 g (or with documented 1 g comparisons)
    analogue    = investigations tagged partial_gravity_analogue (E-FIELD Flames)
    statement   = fixed template naming the scenario gravity, stating that PSI holds no partial-gravity
                  combustion data yet, that microgravity and normal-gravity results bound the behaviour,
                  and that LUCI and FM2 are expected to add data
```

The statement template lives in `presets.yaml` (key `texts.gravity_bounding`) so the UI, the API and the agent use the same words.

## 5. Parameter-space gaps (`/insights/gaps`)

Grid: oxygen fraction bins of 0.05 from 0.10 to 1.00; pressure bins of 10 kPa from 20 to 110. A cell is a gap when no run (explicit or aggregate range) covers it. The response lists contiguous gap regions that intersect the lunar-habitat envelope (oxygen at or above 0.30 and pressure at or below 70.3 kPa) first.

## 6. Worked example (for unit tests)

Weights (habitat defaults) and values: `fuel_realism` 5, `atmosphere_match` 3, `flow_regime` null, `phenomenon` 4, `gravity_bounding` 2.

```
N weights sum = 0.25 + 0.25 + 0.20 + 0.15 = 0.85
weighted sum  = 0.25*5 + 0.25*3 + 0.20*4 + 0.15*2 = 1.25 + 0.75 + 0.80 + 0.30 = 3.10
lens_score    = 20 * 3.10 / 0.85 = 72.94  -> 72.9
confidence    = 0.85
```

Scenario example: ranges o2 [0.10, 0.85], pressure [50, 101.3], flow [0, 60]; scenario o2 0.34, pressure 56.5, flow 10, fuel PMMA; run o2 0.21, pressure 101.3, flow 20, fuel PMMA.

```
num_o2   = |0.34-0.21| / 0.75      = 0.1733
num_p    = |56.5-101.3| / 51.3     = 0.8733
num_flow = |10-20| / 60            = 0.1667
fuel     = 0
distance = 0.35*0.1733 + 0.25*0.8733 + 0.15*0.1667 + 0.25*0 = 0.0607 + 0.2183 + 0.0250 = 0.3040
similarity = 0.696
```
