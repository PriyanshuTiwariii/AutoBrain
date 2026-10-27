/**
 * Types for the engine's contracts (../contracts/needs.schema.json and result.schema.json).
 * The contracts are the source of truth: change them first, then these.
 */

export type Feature =
  | "adas"
  | "camera_360"
  | "sunroof"
  | "ventilated_seats"
  | "esp"
  | "awd"
  | "seven_seats"
  | "lifetime_battery_warranty"
  | "crash_tested"
  | "charger_included"
  | "adaptive_suspension";

export type Priority = "balanced" | "safety" | "cost" | "range" | "features" | "space";
export type HomeCharging = "yes" | "no" | "unsure";
export type RoadConditions = "city_highway" | "rough_roads" | "light_offroad";

/** What the website sends: the required fields plus the ones the form collects. */
export interface NeedsInput {
  budget_max_inr: number;
  seats_min: number;
  daily_km: number;
  longest_regular_trip_km?: number;
  home_charging: HomeCharging;
  must_haves: Feature[];
  nice_to_haves: Feature[];
  priority: Priority;
  road_conditions: RoadConditions;
}

export type SlotKind =
  | "best_match"
  | "same_model"
  | "strong_alternative"
  | "in_between"
  | "dont_overpay"
  | "not_recommended";

export type PriceStatus = "verified" | "corroborated" | "pending";
export type Confidence = "High" | "Medium" | "Low" | "";

export interface ReasonCode {
  code: string;
  detail?: string | null;
}

/** Card figures, already worded by the engine. Numbers and nulls only come from the Result. */
export interface Metrics {
  brand?: string;
  model?: string;
  variant?: string;
  body_type?: string;
  drive?: string;
  battery_kwh?: number | null;
  range_display?: string | null;
  range_test_note?: string | null;
  efficiency_display?: string | null;
  running_cost_inr_per_km?: number | null;
  tariff_basis?: string | null;
  cost_to_own_5yr_inr?: number | null;
  electricity_5yr_inr?: number | null;
  charger_note?: string | null;
  ncap_display?: string | null;
  dc_avg_kw_est?: number | null;
  dc_display?: string | null;
  minutes_dc_per_100km?: number | null;
  seats?: number | null;
  boot_l?: number | null;
  ground_clearance_mm?: number | null;
  battery_clearance_mm?: number | null;
  relative_label?: string | null;
  [key: string]: string | number | null | undefined;
}

export interface Slot {
  slot: SlotKind;
  variant_key: string;
  match_score: number;
  confidence: Confidence;
  price_inr: number;
  price_status: PriceStatus;
  metrics: Metrics;
  reasons: ReasonCode[];
  tradeoffs: ReasonCode[];
  watch_outs: string[];
  savings_vs_best_inr?: number | null;
}

/** Present only when no variant meets every need (contracts/result.schema.json, no_match). */
export interface NoMatch {
  reasons: string[];
  closest_variant_key: string | null;
  what_it_would_take: string[];
}

export interface Result {
  result_id: string;
  dataset_version: string;
  engine_version: string;
  needs_summary: string[];
  slots: Slot[];
  unknowns: string[];
  disclaimer: string;
  no_match?: NoMatch | null;
}

export type ExtractStatus = "read" | "partial" | "off_topic" | "unavailable";
export type RequiredField = "budget_max_inr" | "seats_min" | "daily_km" | "home_charging";

/** What the engine's /extract returns (contracts/extract.response.schema.json). */
export interface ExtractResponse {
  status: ExtractStatus;
  complete: boolean;
  /** Only fields that were read and validated by the engine. */
  needs: Partial<{
    budget_max_inr: number;
    seats_min: number;
    daily_km: number;
    longest_regular_trip_km: number;
    home_charging: HomeCharging;
    must_haves: Feature[];
    nice_to_haves: Feature[];
    priority: Priority;
    road_conditions: RoadConditions;
    pricing_pref: string;
    body_types: string[];
    exclude_models: string[];
  }>;
  missing: RequiredField[];
  question: string | null;
  source: "primary" | "fallback" | null;
  message: string | null;
}

/** What is known about the buyer so far: any subset of the Needs fields (contracts/questions.request.schema.json). */
export type PartialNeeds = Partial<NeedsInput>;

export type OptionalField = "road_conditions" | "priority" | "longest_regular_trip_km";
export type QuestionField = RequiredField | OptionalField;

export interface QuestionCard {
  id: string;
  label: string;
  sublabel: string | null;
  /** Needs fields to set when the buyer taps the card. Empty for "Not sure" on an optional question. */
  patch: PartialNeeds;
}

/** What the engine's /next_question returns (contracts/questions.response.schema.json). */
export interface QuestionResponse {
  done: boolean;
  kind: "required" | "optional" | "none";
  field: QuestionField | null;
  question: string | null;
  why: string | null;
  example: string | null;
  cards: QuestionCard[];
  helper: "budget_emi" | "commute_minutes" | null;
  can_show_results: boolean;
  missing_required: RequiredField[];
}

/** A problem with one field, as the engine and the website's server route report it. */
export interface FieldProblem {
  field: string;
  message: string;
}
