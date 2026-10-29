import { formatLakh } from "./format";
import type { CarOption, CarsResponse, CompareResponse } from "./types";

export const MIN_CARS = 2;
export const MAX_CARS = 3;

const isObject = (v: unknown): v is Record<string, unknown> => !!v && typeof v === "object" && !Array.isArray(v);

export function isCarsResponse(value: unknown): value is CarsResponse {
  if (!isObject(value) || typeof value.dataset_version !== "string" || !Array.isArray(value.cars)) return false;
  return value.cars.every(
    (c) =>
      isObject(c) &&
      typeof c.variant_key === "string" &&
      typeof c.brand === "string" &&
      typeof c.model === "string" &&
      typeof c.variant === "string" &&
      (c.pricing_type === "battery included" || c.pricing_type === "BaaS"),
  );
}

export function isCompareResponse(value: unknown): value is CompareResponse {
  if (!isObject(value)) return false;
  const cars = value.cars;
  if (!Array.isArray(cars) || cars.length < MIN_CARS || cars.length > MAX_CARS) return false;
  if (!Array.isArray(value.winners) || !Array.isArray(value.sections) || !Array.isArray(value.notes) || !Array.isArray(value.watch_outs)) return false;
  return value.sections.every(
    (s) =>
      isObject(s) &&
      typeof s.title === "string" &&
      Array.isArray(s.rows) &&
      s.rows.every((r) => isObject(r) && typeof r.label === "string" && Array.isArray(r.cells) && r.cells.length === cars.length),
  );
}

/** "?cars=a,b,c" → the keys, trimmed, without repeats, at most three. Anything else is ignored. */
export function parseCarsParam(value: string | null | undefined): string[] {
  if (!value) return [];
  return [...new Set(value.split(",").map((k) => k.trim()).filter((k) => /^[A-Za-z0-9._-]{1,80}$/.test(k)))].slice(0, MAX_CARS);
}

export function compareHref(keys: string[]): string {
  return keys.length > 0 ? `/compare?cars=${keys.map(encodeURIComponent).join(",")}` : "/compare";
}

/** Battery-rental (BaaS) versions are hidden from the pickers unless the buyer asks for them. */
const visible = (cars: CarOption[], includeBaas: boolean) => cars.filter((c) => includeBaas || c.pricing_type !== "BaaS");

export function brandsOf(cars: CarOption[], includeBaas: boolean): string[] {
  return [...new Set(visible(cars, includeBaas).map((c) => c.brand))].sort();
}

export function modelsOf(cars: CarOption[], brand: string, includeBaas: boolean): string[] {
  return [...new Set(visible(cars, includeBaas).filter((c) => c.brand === brand).map((c) => c.model))].sort();
}

export function variantsOf(cars: CarOption[], brand: string, model: string, includeBaas: boolean): CarOption[] {
  return visible(cars, includeBaas)
    .filter((c) => c.brand === brand && c.model === model)
    .sort((a, b) => (a.price_inr ?? Number.MAX_SAFE_INTEGER) - (b.price_inr ?? Number.MAX_SAFE_INTEGER) || a.variant.localeCompare(b.variant));
}

export function variantLabel(car: CarOption): string {
  const price = car.price_status === "pending" || car.price_inr == null ? "price not confirmed" : formatLakh(car.price_inr);
  return `${car.variant} (${price}${car.pricing_type === "BaaS" ? ", battery rental" : ""})`;
}
