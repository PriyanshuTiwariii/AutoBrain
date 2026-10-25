import type { Confidence, PriceStatus, SlotKind } from "./types";

/**
 * Rupees as the engine words them: ₹6.99 lakh, ₹2 lakh, ₹60,000 below one lakh.
 * Same rule as the engine's fmt_lakh; this only formats a number that came from the Result.
 */
export function formatLakh(inr: number): string {
  if (Math.abs(inr) < 100_000) return `₹${inr.toLocaleString("en-IN")}`;
  const lakh = inr / 100_000;
  return Number.isInteger(lakh) ? `₹${lakh} lakh` : `₹${lakh.toFixed(2)} lakh`;
}

export const PRICE_STATUS_LABEL: Record<PriceStatus, string> = {
  verified: "Official ex-showroom price",
  corroborated: "Ex-showroom price confirmed by more than one source; check before buying",
  pending: "Price not yet confirmed",
};

export const CONFIDENCE_LABEL: Record<Exclude<Confidence, "">, string> = {
  High: "High data confidence",
  Medium: "Medium data confidence",
  Low: "Low data confidence",
};

export const SLOT_LABEL: Record<SlotKind, string> = {
  best_match: "Best match",
  same_model: "Same model, one step up",
  strong_alternative: "Strong alternative",
  in_between: "In between",
  dont_overpay: "Don't overpay",
  not_recommended: "Considered, not recommended",
};

export const DRIVE_LABEL: Record<string, string> = {
  FWD: "front-wheel drive",
  RWD: "rear-wheel drive",
  AWD: "all-wheel drive",
};

export const NOT_STATED = "Not stated by maker";

/** "Tata Nexon.ev Empowered+ A 45" from the card's metrics. */
export function carName(metrics: { brand?: string; model?: string; variant?: string }, fallback: string): string {
  const parts = [metrics.brand, metrics.model, metrics.variant].filter(Boolean);
  return parts.length ? parts.join(" ") : fallback;
}
