import { CONFIDENCE_LABEL, DRIVE_LABEL, NOT_STATED, PRICE_STATUS_LABEL, SLOT_LABEL, carName, formatLakh } from "@/lib/format";
import type { Metrics, Slot } from "@/lib/types";

const CHECK = (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#1F7A3A" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="mt-0.5 flex-none">
    <path d="M20 6 9 17l-5-5" />
  </svg>
);
const WARN = (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#B4460B" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="mt-0.5 flex-none">
    <path d="M12 9v4M12 17h.01" />
    <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
  </svg>
);

const DOT = <span className="mt-2 h-2 w-2 flex-none rounded-full bg-muted" aria-hidden="true" />;

/** Heading for the reasons list. Cards about a cheaper pick describe what changes, not why it "fits". */
const REASONS_HEADING: Record<Slot["slot"], string> = {
  best_match: "Why it fits you",
  same_model: "Why consider the step up",
  strong_alternative: "Why consider it",
  in_between: "What changes",
  dont_overpay: "The saving, and what it costs you",
  not_recommended: "Why not",
};

interface Tile {
  label: string;
  value: string;
  sub?: string;
}

/** The figures on a card. Every value is the engine's own wording or a number from the Result. */
export function tilesFor(m: Metrics, featured: boolean): Tile[] {
  const tiles: Tile[] = [
    { label: "Range", value: m.range_display ?? NOT_STATED, sub: m.range_test_note ?? undefined },
  ];
  if (m.efficiency_display) tiles.push({ label: "Efficiency", value: m.efficiency_display });
  if (typeof m.running_cost_inr_per_km === "number") {
    tiles.push({
      label: "Running cost",
      value: `₹${m.running_cost_inr_per_km.toFixed(2)}/km`,
      sub: m.tariff_basis ?? undefined,
    });
  }
  if (typeof m.cost_to_own_5yr_inr === "number") {
    tiles.push({
      label: "5-year cost to own",
      value: `~${formatLakh(m.cost_to_own_5yr_inr)}`,
      sub:
        typeof m.electricity_5yr_inr === "number"
          ? `Price + charger + ~${formatLakh(m.electricity_5yr_inr)} electricity`
          : "Price + charger + electricity",
    });
  }
  tiles.push({ label: "Crash test (adult)", value: m.ncap_display ?? NOT_STATED });
  if (m.charger_note) tiles.push({ label: "Home charger", value: m.charger_note });
  if (featured) {
    if (m.dc_display) tiles.push({ label: "DC fast charging", value: m.dc_display });
    tiles.push({ label: "Seats", value: m.seats != null ? String(m.seats) : NOT_STATED });
    tiles.push({ label: "Boot", value: m.boot_l != null ? `${m.boot_l} L` : NOT_STATED });
    tiles.push({
      label: "Ground clearance",
      value: m.ground_clearance_mm != null ? `${m.ground_clearance_mm} mm` : NOT_STATED,
    });
  }
  return tiles;
}

function subtitle(m: Metrics): string {
  const parts: string[] = [];
  if (m.body_type) parts.push(m.body_type);
  if (typeof m.battery_kwh === "number") parts.push(`${m.battery_kwh} kWh`);
  if (m.drive && DRIVE_LABEL[m.drive]) parts.push(DRIVE_LABEL[m.drive] as string);
  return parts.join(" · ");
}

function ConfidenceBadge({ confidence }: { confidence: Slot["confidence"] }) {
  if (!confidence) return null;
  const tone =
    confidence === "High"
      ? "bg-good-bg text-good-ink"
      : confidence === "Medium"
        ? "bg-warn-bg text-warn-ink"
        : "bg-chip text-ink";
  return <span className={`rounded-md px-2.5 py-1 text-[13px] font-bold ${tone}`}>{CONFIDENCE_LABEL[confidence]}</span>;
}

function Price({ slot, big }: { slot: Slot; big: boolean }) {
  const known = slot.price_status !== "pending" && slot.price_inr > 0;
  return (
    <div className="flex flex-col gap-0.5">
      <div className={`font-mono font-semibold ${big ? "text-[26px] md:text-[34px]" : "text-[22px]"}`}>
        {known ? formatLakh(slot.price_inr) : "Price not confirmed"}
      </div>
      <div className="max-w-[260px] text-xs text-muted">{PRICE_STATUS_LABEL[slot.price_status]}</div>
    </div>
  );
}

export default function SlotCard({ slot, featured = false }: { slot: Slot; featured?: boolean }) {
  const m = slot.metrics;
  const name = carName(m, slot.variant_key);
  const isDontOverpay = slot.slot === "dont_overpay";
  const isTradeDown = isDontOverpay || slot.slot === "in_between";
  const fitLabel = m.relative_label || null; // only cards that compete for the top spot carry one

  const frame = featured
    ? "border-2 border-brand p-5 md:p-7 rounded-[20px]"
    : isDontOverpay
      ? "border-2 border-warn p-5 md:p-6 rounded-[18px]"
      : "border border-line p-5 md:p-6 rounded-[18px]";
  const tag = featured ? "bg-brand text-white" : isDontOverpay ? "bg-warn-bg text-warn-ink" : "bg-chip text-ink";

  return (
    <article className={`no-break flex flex-col gap-5 bg-white ${frame}`} aria-label={SLOT_LABEL[slot.slot]}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 flex-1 basis-64 flex-col gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className={`rounded-md px-2.5 py-1 text-xs font-extrabold uppercase tracking-[0.08em] ${tag}`}>
              {SLOT_LABEL[slot.slot]}
            </span>
            {fitLabel ? (
              <span className="rounded-md bg-sky px-2.5 py-1 text-[13px] font-bold text-brand-dark">{fitLabel}</span>
            ) : null}
            <ConfidenceBadge confidence={slot.confidence} />
          </div>
          <h2 className={`m-0 font-extrabold leading-tight tracking-tight ${featured ? "text-[22px] md:text-[30px]" : "text-xl"}`}>
            {name}
          </h2>
          <div className="text-[15px] text-muted">{subtitle(m)}</div>
        </div>
        <div className="flex flex-wrap items-center gap-4">
          <Price slot={slot} big={featured} />
          {slot.savings_vs_best_inr ? (
            <div className="rounded-[14px] bg-warn px-4 py-3 text-center text-white">
              <div className="text-xs font-bold">Saves</div>
              <div className="font-mono text-xl font-semibold">{formatLakh(slot.savings_vs_best_inr)}</div>
              <div className="text-[11px]">vs the top pick</div>
            </div>
          ) : null}
        </div>
      </div>

      <div className={`grid grid-cols-2 gap-2.5 ${featured ? "md:grid-cols-4" : "md:grid-cols-3"}`}>
        {tilesFor(m, featured).map((t) => (
          <div key={t.label} className="flex flex-col gap-1 rounded-xl bg-surface p-3 md:p-3.5">
            <div className="text-[11px] font-bold text-muted md:text-xs">{t.label}</div>
            <div className="break-words font-mono text-[15px] font-semibold leading-snug md:text-base">{t.value}</div>
            {t.sub ? <div className="text-xs leading-snug text-muted">{t.sub}</div> : null}
          </div>
        ))}
      </div>

      <div className={`grid gap-5 ${featured ? "md:grid-cols-2" : ""}`}>
        {slot.reasons.length > 0 ? (
          <div className="flex flex-col gap-3">
            <h3 className="m-0 text-base font-extrabold">{REASONS_HEADING[slot.slot]}</h3>
            {slot.reasons.map((r, i) => (
              <div key={`${r.code}-${i}`} className="flex items-start gap-2.5">
                {isTradeDown ? DOT : CHECK}
                <div className="text-[15px] leading-relaxed">{r.detail ?? r.code}</div>
              </div>
            ))}
          </div>
        ) : null}

        {slot.tradeoffs.length > 0 ? (
          <div className="flex flex-col gap-3">
            <h3 className="m-0 text-base font-extrabold text-warn-ink">Trade-offs to know</h3>
            {slot.tradeoffs.map((t, i) => (
              <div key={`${t.code}-${i}`} className="flex items-start gap-2.5">
                {WARN}
                <div className="text-[15px] leading-relaxed">{t.detail ?? t.code}</div>
              </div>
            ))}
          </div>
        ) : null}
      </div>

      {slot.watch_outs.length > 0 ? (
        <div className="flex flex-col gap-3 rounded-[14px] border border-warn-line bg-warn-bg p-4">
          <h3 className="m-0 text-base font-extrabold text-warn-ink">Watch out for</h3>
          {slot.watch_outs.map((w, i) => (
            <div key={`${w}-${i}`} className="flex items-start gap-2.5">
              {WARN}
              <div className="text-[15px] leading-relaxed">{w}</div>
            </div>
          ))}
        </div>
      ) : null}
    </article>
  );
}
