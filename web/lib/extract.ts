import { FEATURES, LIMITS, type FormState } from "./needs";
import type { ExtractResponse, ExtractStatus, Feature, HomeCharging, Priority, RequiredField, RoadConditions } from "./types";

export const EXTRACT_STATUSES: ExtractStatus[] = ["read", "partial", "off_topic", "unavailable"];
export const REQUIRED_FIELDS: RequiredField[] = ["budget_max_inr", "seats_min", "daily_km", "home_charging"];

export const MAX_TEXT_CHARS = 1500; // contracts/extract.request.schema.json

/** What the page shows when describing isn't available; the form works exactly as before. */
export const UNAVAILABLE: ExtractResponse = {
  status: "unavailable",
  complete: false,
  needs: {},
  missing: [...REQUIRED_FIELDS],
  question: null,
  source: null,
  message: "Describing your needs isn't available right now. Please fill in the form below.",
};

const HOME_CHARGING: HomeCharging[] = ["yes", "no", "unsure"];
const ROAD_CONDITIONS: RoadConditions[] = ["city_highway", "rough_roads", "light_offroad"];
const PRIORITIES: Priority[] = ["balanced", "safety", "cost", "range", "features", "space"];

export function isExtractResponse(value: unknown): value is ExtractResponse {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return (
    EXTRACT_STATUSES.includes(v.status as ExtractStatus) &&
    typeof v.complete === "boolean" &&
    !!v.needs &&
    typeof v.needs === "object" &&
    !Array.isArray(v.needs) &&
    Array.isArray(v.missing) &&
    (v.question === null || typeof v.question === "string") &&
    (v.message === null || typeof v.message === "string")
  );
}

const FIELD_LABEL = {
  budget: "budget",
  seats: "seats",
  dailyKm: "daily driving",
  tripKm: "longest trip",
  homeCharging: "home charging",
  mustHaves: "must-haves",
  niceToHaves: "nice-to-haves",
  priority: "priority",
  roadConditions: "road conditions",
} as const;

/** Fields the engine can read that the form has no input for (yet). They are not applied. */
const NOT_IN_FORM: Record<string, string> = {
  pricing_pref: "pricing",
  body_types: "body type",
  exclude_models: "excluded cars",
};

const FEATURE_VALUES = new Set<string>(FEATURES.map((f) => f.value));
const keepFeatures = (list: unknown): Feature[] =>
  Array.isArray(list) ? (list.filter((f) => typeof f === "string" && FEATURE_VALUES.has(f)) as Feature[]) : [];

/** 1_500_000 → "15", 1_250_000 → "12.5": the lakh figure the budget box shows. */
export function lakhText(inr: number): string {
  return String(Number((inr / 100_000).toFixed(4)));
}

export interface Applied {
  form: FormState;
  /** Form fields that were filled in, in words. */
  filled: string[];
  /** Things the engine read that the form cannot take, in words. */
  ignored: string[];
}

/**
 * Put what was read into the form. Only fields the engine returned are touched; everything the buyer
 * already typed stays. The values are the engine's, already validated: nothing is calculated here
 * except showing rupees as lakh.
 */
export function applyExtraction(form: FormState, response: ExtractResponse): Applied {
  const next: FormState = { ...form, mustHaves: [...form.mustHaves], niceToHaves: [...form.niceToHaves] };
  const filled: string[] = [];
  const n = response.needs;

  if (typeof n.budget_max_inr === "number" && n.budget_max_inr >= LIMITS.budgetMinInr) {
    next.budgetLakh = lakhText(n.budget_max_inr);
    filled.push(FIELD_LABEL.budget);
  }
  if (typeof n.seats_min === "number" && n.seats_min >= LIMITS.seatsMin && n.seats_min <= LIMITS.seatsMax) {
    next.seats = String(n.seats_min);
    filled.push(FIELD_LABEL.seats);
  }
  if (typeof n.daily_km === "number" && n.daily_km >= LIMITS.dailyKmMin && n.daily_km <= LIMITS.dailyKmMax) {
    next.dailyKm = String(n.daily_km);
    filled.push(FIELD_LABEL.dailyKm);
  }
  if (typeof n.longest_regular_trip_km === "number" && n.longest_regular_trip_km >= LIMITS.tripKmMin) {
    next.tripKm = String(n.longest_regular_trip_km);
    filled.push(FIELD_LABEL.tripKm);
  }
  if (n.home_charging && HOME_CHARGING.includes(n.home_charging)) {
    next.homeCharging = n.home_charging;
    filled.push(FIELD_LABEL.homeCharging);
  }
  const must = keepFeatures(n.must_haves);
  if (must.length > 0) {
    next.mustHaves = must;
    next.niceToHaves = next.niceToHaves.filter((f) => !must.includes(f));
    filled.push(FIELD_LABEL.mustHaves);
  }
  const nice = keepFeatures(n.nice_to_haves).filter((f) => !next.mustHaves.includes(f));
  if (nice.length > 0) {
    next.niceToHaves = nice;
    filled.push(FIELD_LABEL.niceToHaves);
  }
  if (n.priority && PRIORITIES.includes(n.priority)) {
    next.priority = n.priority;
    filled.push(FIELD_LABEL.priority);
  }
  if (n.road_conditions && ROAD_CONDITIONS.includes(n.road_conditions)) {
    next.roadConditions = n.road_conditions;
    filled.push(FIELD_LABEL.roadConditions);
  }

  const ignored = Object.entries(NOT_IN_FORM)
    .filter(([key]) => {
      const value = (n as Record<string, unknown>)[key];
      return Array.isArray(value) ? value.length > 0 : value != null;
    })
    .map(([, label]) => label);

  return { form: next, filled, ignored };
}

export interface Note {
  tone: "ok" | "info" | "warn";
  /** Short lines for the box, in order. */
  lines: string[];
}

/** What the box says after an answer. The engine's own message and question are shown as they came. */
export function noteFor(response: ExtractResponse, applied: Applied): Note {
  if (response.status === "unavailable") return { tone: "info", lines: [response.message ?? UNAVAILABLE.message ?? ""] };
  if (response.status === "off_topic") return { tone: "info", lines: [response.message ?? ""].filter(Boolean) };

  const lines: string[] = [];
  if (applied.filled.length > 0) {
    lines.push(`We filled in: ${applied.filled.join(", ")}. Check every field below and change anything that is wrong, then press "Show my shortlist".`);
  }
  if (response.message) lines.push(response.message);
  if (applied.ignored.length > 0) {
    lines.push(`We also heard about ${applied.ignored.join(", ")}, but the form cannot use that yet, so it was not applied.`);
  }
  if (response.question) lines.push(`One more thing: ${response.question}`);
  return { tone: response.status === "partial" ? "warn" : "ok", lines };
}
