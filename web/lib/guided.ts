import { FEATURES, LIMITS, buildNeeds, type FormState, EMPTY_FORM } from "./needs";
import { lakhText } from "./extract";
import type {
  ExtractResponse, Feature, FieldProblem, NeedsInput, OptionalField, PartialNeeds, QuestionField, QuestionResponse,
} from "./types";

/**
 * The guided flow's logic. The engine chooses the questions and the answer cards (each card carries the Needs
 * fields it sets); this file only keeps the answers, shows them back in plain words, and does two small
 * calculators whose assumptions are always shown and confirmed by the buyer. Nothing here ranks or scores a car.
 */

export const OPTIONAL_FIELDS: OptionalField[] = ["road_conditions", "priority", "longest_regular_trip_km"];

const NEEDS_KEYS: (keyof NeedsInput)[] = [
  "budget_max_inr", "seats_min", "daily_km", "longest_regular_trip_km", "home_charging",
  "must_haves", "nice_to_haves", "priority", "road_conditions",
];

export function isQuestionResponse(value: unknown): value is QuestionResponse {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.done === "boolean" &&
    (v.kind === "required" || v.kind === "optional" || v.kind === "none") &&
    (v.field === null || typeof v.field === "string") &&
    (v.question === null || typeof v.question === "string") &&
    Array.isArray(v.cards) &&
    v.cards.every((c) => c && typeof c === "object" && typeof (c as { id?: unknown }).id === "string" && typeof (c as { label?: unknown }).label === "string" && !!(c as { patch?: unknown }).patch && typeof (c as { patch?: unknown }).patch === "object") &&
    typeof v.can_show_results === "boolean" &&
    Array.isArray(v.missing_required)
  );
}

/** Set what a tapped card says. Only the fields in the patch change. */
export function applyPatch(needs: PartialNeeds, patch: PartialNeeds): PartialNeeds {
  return { ...needs, ...patch };
}

/** Put what the engine read from typed words into the known needs. Values are the engine's, already validated. */
export function mergeExtraction(needs: PartialNeeds, response: ExtractResponse, only?: QuestionField): PartialNeeds {
  const read = response.needs as Record<string, unknown>;
  const next: Record<string, unknown> = { ...needs };
  for (const key of NEEDS_KEYS) {
    if (only && key !== only) continue;
    if (read[key] === undefined || read[key] === null) continue;
    if (Array.isArray(read[key]) && (read[key] as unknown[]).length === 0) continue;
    next[key] = read[key];
  }
  return next as PartialNeeds;
}

/** The asked-list for the engine after an answer: optional fields stay "asked" once answered or skipped. */
export function markAsked(asked: OptionalField[], field: QuestionField | null): OptionalField[] {
  if (!field || !(OPTIONAL_FIELDS as string[]).includes(field)) return asked;
  return asked.includes(field as OptionalField) ? asked : [...asked, field as OptionalField];
}

// --- showing what we understood, in plain words -------------------------------------------------------------

const PRIORITY_WORDS: Record<string, string> = {
  balanced: "A bit of everything",
  safety: "Keeping my family safe",
  cost: "Low running cost",
  range: "Going far without charging",
  features: "A premium, feature-rich car",
  space: "Space and comfort",
};
const ROAD_WORDS: Record<string, string> = {
  city_highway: "Smooth city and highway roads",
  rough_roads: "Potholes and speed breakers",
  light_offroad: "Hills, gravel or village tracks",
};
const CHARGING_WORDS: Record<string, string> = {
  yes: "Can charge at home",
  no: "Cannot charge at home",
  unsure: "Home charging: not sure yet",
};

export interface Chip {
  field: keyof NeedsInput;
  label: string;
  value: string;
}

/** One line per known fact, in the order a buyer thinks of them. */
export function chipsFor(needs: PartialNeeds): Chip[] {
  const chips: Chip[] = [];
  if (needs.budget_max_inr !== undefined) {
    chips.push({ field: "budget_max_inr", label: "Budget", value: `Up to ${lakhText(needs.budget_max_inr)} lakh` });
  }
  if (needs.seats_min !== undefined) chips.push({ field: "seats_min", label: "Seats", value: `${needs.seats_min} or more` });
  if (needs.daily_km !== undefined) chips.push({ field: "daily_km", label: "Daily driving", value: `About ${needs.daily_km} km` });
  if (needs.home_charging !== undefined) {
    chips.push({ field: "home_charging", label: "Parking", value: CHARGING_WORDS[needs.home_charging] ?? needs.home_charging });
  }
  if (needs.road_conditions !== undefined) {
    chips.push({ field: "road_conditions", label: "Roads", value: ROAD_WORDS[needs.road_conditions] ?? needs.road_conditions });
  }
  if (needs.priority !== undefined) {
    chips.push({ field: "priority", label: "Matters most", value: PRIORITY_WORDS[needs.priority] ?? needs.priority });
  }
  if (needs.longest_regular_trip_km !== undefined) {
    chips.push({ field: "longest_regular_trip_km", label: "Long trips", value: `About ${needs.longest_regular_trip_km} km one way` });
  }
  const names = (list: Feature[]) => list.map((f) => FEATURES.find((x) => x.value === f)?.label ?? f).join(", ");
  if (needs.must_haves?.length) chips.push({ field: "must_haves", label: "Must have", value: names(needs.must_haves) });
  if (needs.nice_to_haves?.length) chips.push({ field: "nice_to_haves", label: "Would like", value: names(needs.nice_to_haves) });
  return chips;
}

/** "Change" on a chip: forget that one answer. A forgotten required answer is simply asked again. */
export function removeField(needs: PartialNeeds, field: keyof NeedsInput): PartialNeeds {
  const next = { ...needs };
  delete next[field];
  return next;
}

// --- to and from the form (so "Edit my needs" and the advanced form keep working) ----------------------------

export function toFormState(needs: PartialNeeds): FormState {
  return {
    ...EMPTY_FORM,
    budgetLakh: needs.budget_max_inr !== undefined ? lakhText(needs.budget_max_inr) : "",
    seats: needs.seats_min !== undefined ? String(needs.seats_min) : EMPTY_FORM.seats,
    dailyKm: needs.daily_km !== undefined ? String(needs.daily_km) : "",
    tripKm: needs.longest_regular_trip_km !== undefined ? String(needs.longest_regular_trip_km) : "",
    homeCharging: needs.home_charging ?? "",
    mustHaves: needs.must_haves ?? [],
    niceToHaves: needs.nice_to_haves ?? [],
    priority: needs.priority ?? EMPTY_FORM.priority,
    roadConditions: needs.road_conditions ?? EMPTY_FORM.roadConditions,
  };
}

/**
 * Saved form → what is known. Only a form that is complete and valid counts; otherwise nothing is assumed.
 * The form's built-in defaults (balanced, city and highway, no must-haves) are not answers, so they are dropped.
 */
export function formToPartial(form: FormState): PartialNeeds {
  const { needs } = buildNeeds(form);
  if (!needs) return {};
  const known: PartialNeeds = { ...needs };
  if (known.priority === EMPTY_FORM.priority) delete known.priority;
  if (known.road_conditions === EMPTY_FORM.roadConditions) delete known.road_conditions;
  if (known.must_haves?.length === 0) delete known.must_haves;
  if (known.nice_to_haves?.length === 0) delete known.nice_to_haves;
  return known;
}

/**
 * Known needs → what the engine's /recommend takes. Home charging still unknown becomes "unsure" (never yes
 * or no); budget, seats and daily km are never filled in.
 */
export function toRecommendNeeds(needs: PartialNeeds): { needs?: NeedsInput; problems: FieldProblem[] } {
  const missing = (["budget_max_inr", "seats_min", "daily_km"] as const).filter((f) => needs[f] === undefined);
  if (missing.length > 0) {
    return { problems: missing.map((field) => ({ field, message: "We still need this answer before we can suggest cars." })) };
  }
  return buildNeeds(toFormState({ ...needs, home_charging: needs.home_charging ?? "unsure" }));
}

// --- the two small calculators (assumptions are shown on screen and the buyer confirms the result) ---------------

/** Defaults the buyer can change on screen. Demo estimates only: real rates depend on the lender and the buyer. */
export const EMI_ASSUMPTIONS = { annualRatePercent: 9, maxRatePercent: 30, roundToInr: 50_000 };
export const COMMUTE_ASSUMPTIONS = { averageSpeedKmh: 20, minSpeedKmh: 5, maxSpeedKmh: 80 };

/**
 * What a monthly EMI plus a down payment can buy: the loan the EMI repays over the years at the assumed rate, plus
 * the down payment, rounded down to the nearest 50,000. Null when the answer would be under the minimum budget.
 */
export function loanFromEmi(monthlyEmiInr: number, years: number, annualRatePercent: number): number | null {
  if (![monthlyEmiInr, years, annualRatePercent].every(Number.isFinite) || monthlyEmiInr <= 0 || years <= 0) return null;
  if (annualRatePercent <= 0 || annualRatePercent > EMI_ASSUMPTIONS.maxRatePercent) return null;
  const r = annualRatePercent / 100 / 12;
  return (monthlyEmiInr * (1 - Math.pow(1 + r, -Math.round(years * 12)))) / r;
}

export function budgetFromEmi(
  monthlyEmiInr: number, years: number, downPaymentInr: number, annualRatePercent: number = EMI_ASSUMPTIONS.annualRatePercent,
): number | null {
  const loan = loanFromEmi(monthlyEmiInr, years, annualRatePercent);
  if (loan === null || !Number.isFinite(downPaymentInr) || downPaymentInr < 0) return null;
  const budget = Math.floor((loan + downPaymentInr) / EMI_ASSUMPTIONS.roundToInr) * EMI_ASSUMPTIONS.roundToInr;
  return budget >= LIMITS.budgetMinInr ? budget : null;
}

/** A daily total from minutes of travel one way: minutes at the average speed, there and back. */
export function dailyKmFromCommuteMinutes(
  minutesOneWay: number, averageSpeedKmh: number = COMMUTE_ASSUMPTIONS.averageSpeedKmh,
): number | null {
  if (![minutesOneWay, averageSpeedKmh].every(Number.isFinite) || minutesOneWay <= 0) return null;
  if (averageSpeedKmh < COMMUTE_ASSUMPTIONS.minSpeedKmh || averageSpeedKmh > COMMUTE_ASSUMPTIONS.maxSpeedKmh) return null;
  const km = Math.round(((minutesOneWay * averageSpeedKmh) / 60) * 2);
  return km >= LIMITS.dailyKmMin && km <= LIMITS.dailyKmMax ? km : null;
}
