import type { FieldProblem, Feature, HomeCharging, NeedsInput, Priority, RoadConditions } from "./types";

/** Limits from ../contracts/needs.schema.json (a test keeps these in step with the contract). */
export const LIMITS = {
  budgetMinInr: 300_000,
  seatsMin: 2,
  seatsMax: 7,
  dailyKmMin: 1,
  dailyKmMax: 500,
  tripKmMin: 1,
};

export const FEATURES: { value: Feature; label: string }[] = [
  { value: "adas", label: "ADAS (driver assistance)" },
  { value: "camera_360", label: "360° camera" },
  { value: "sunroof", label: "Sunroof" },
  { value: "ventilated_seats", label: "Ventilated front seats" },
  { value: "esp", label: "ESP (stability control)" },
  { value: "awd", label: "All-wheel drive" },
  { value: "seven_seats", label: "7 seats" },
  { value: "lifetime_battery_warranty", label: "Lifetime battery warranty" },
  { value: "crash_tested", label: "Bharat NCAP crash-tested" },
  { value: "charger_included", label: "Home charger included" },
  { value: "adaptive_suspension", label: "Adaptive suspension" },
];

export const PRIORITIES: { value: Priority; label: string; hint: string }[] = [
  { value: "balanced", label: "Balanced", hint: "A bit of everything" },
  { value: "safety", label: "Safety", hint: "Crash tests, ESP, ADAS" },
  { value: "cost", label: "Lowest cost", hint: "Cheapest to own over 5 years" },
  { value: "range", label: "Range", hint: "Go further on a charge" },
  { value: "features", label: "Features", hint: "Comfort and tech" },
  { value: "space", label: "Space", hint: "Seats and boot" },
];

export const HOME_CHARGING_OPTIONS: { value: HomeCharging; label: string; hint: string }[] = [
  { value: "yes", label: "Yes", hint: "I can install a charger at home" },
  { value: "no", label: "No", hint: "I would rely on public chargers" },
  { value: "unsure", label: "Not sure", hint: "I'll find out" },
];

export const ROAD_CONDITIONS: { value: RoadConditions; label: string; hint: string }[] = [
  { value: "city_highway", label: "City and highway", hint: "Normal paved roads" },
  { value: "rough_roads", label: "Rough roads", hint: "Potholes, speed breakers, broken roads" },
  { value: "light_offroad", label: "Light off-road", hint: "Gravel, dirt tracks (not serious off-roading)" },
];

/** Everything the form holds, as the strings the inputs hold. */
export interface FormState {
  budgetLakh: string;
  seats: string;
  dailyKm: string;
  tripKm: string;
  homeCharging: HomeCharging | "";
  mustHaves: Feature[];
  niceToHaves: Feature[];
  priority: Priority;
  roadConditions: RoadConditions;
}

export const EMPTY_FORM: FormState = {
  budgetLakh: "",
  seats: "5",
  dailyKm: "",
  tripKm: "",
  homeCharging: "",
  mustHaves: [],
  niceToHaves: [],
  priority: "balanced",
  roadConditions: "city_highway",
};

/** The form field each engine field belongs to (so an engine message lands under the right input). */
const ENGINE_FIELD_TO_FORM: Record<string, string> = {
  budget_max_inr: "budgetLakh",
  seats_min: "seats",
  daily_km: "dailyKm",
  longest_regular_trip_km: "tripKm",
  home_charging: "homeCharging",
  must_haves: "mustHaves",
  nice_to_haves: "niceToHaves",
  priority: "priority",
  road_conditions: "roadConditions",
};

export function formFieldFor(field: string): string {
  const base = field.replace(/\[\d+\]$/, "");
  if (Object.values(ENGINE_FIELD_TO_FORM).includes(base)) return base; // already a form field
  return ENGINE_FIELD_TO_FORM[base] ?? "form";
}

function wholeNumber(text: string): number | null {
  const trimmed = text.trim();
  if (!/^\d+$/.test(trimmed)) return null;
  return Number(trimmed);
}

/** Form → Needs. Rupees are computed here once (lakh × 100,000); everything else passes through. */
export function buildNeeds(form: FormState): { needs?: NeedsInput; problems: FieldProblem[] } {
  const problems: FieldProblem[] = [];

  const lakh = Number(form.budgetLakh.trim());
  const budgetOk = form.budgetLakh.trim() !== "" && Number.isFinite(lakh);
  const budgetInr = Math.round(lakh * 100_000);
  if (!budgetOk) {
    problems.push({ field: "budgetLakh", message: "Enter your budget in lakh, for example 15 or 12.5." });
  } else if (budgetInr < LIMITS.budgetMinInr) {
    problems.push({ field: "budgetLakh", message: `The budget must be at least ${LIMITS.budgetMinInr / 100_000} lakh.` });
  }

  const seats = wholeNumber(form.seats);
  if (seats === null || seats < LIMITS.seatsMin || seats > LIMITS.seatsMax) {
    problems.push({ field: "seats", message: `Choose between ${LIMITS.seatsMin} and ${LIMITS.seatsMax} seats.` });
  }

  const dailyKm = wholeNumber(form.dailyKm);
  if (dailyKm === null || dailyKm < LIMITS.dailyKmMin || dailyKm > LIMITS.dailyKmMax) {
    problems.push({
      field: "dailyKm",
      message: `Enter your daily driving as a whole number of km, ${LIMITS.dailyKmMin} to ${LIMITS.dailyKmMax}.`,
    });
  }

  let tripKm: number | null = null;
  if (form.tripKm.trim() !== "") {
    tripKm = wholeNumber(form.tripKm);
    if (tripKm === null || tripKm < LIMITS.tripKmMin) {
      problems.push({ field: "tripKm", message: "Enter the longest trip as a whole number of km, or leave it empty." });
    }
  }

  if (form.homeCharging === "") {
    problems.push({ field: "homeCharging", message: "Tell us whether you can charge at home." });
  }

  if (problems.length > 0 || seats === null || dailyKm === null || form.homeCharging === "") {
    return { problems };
  }

  const needs: NeedsInput = {
    budget_max_inr: budgetInr,
    seats_min: seats,
    daily_km: dailyKm,
    home_charging: form.homeCharging,
    must_haves: form.mustHaves,
    nice_to_haves: form.niceToHaves.filter((f) => !form.mustHaves.includes(f)),
    priority: form.priority,
    road_conditions: form.roadConditions,
  };
  if (tripKm !== null) needs.longest_regular_trip_km = tripKm;
  return { needs, problems };
}
