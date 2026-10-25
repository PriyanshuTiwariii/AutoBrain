import { NOT_STATED, carName, formatLakh } from "@/lib/format";
import type { Slot } from "@/lib/types";

type Row = { label: string; cell: (s: Slot) => string };

// Rows are read straight off each card's figures; nothing is calculated here
const ROWS: Row[] = [
  {
    label: "Price",
    cell: (s) => (s.price_status !== "pending" && s.price_inr > 0 ? `${formatLakh(s.price_inr)} (${s.price_status})` : "Not confirmed"),
  },
  {
    label: "5-year cost",
    cell: (s) => (typeof s.metrics.cost_to_own_5yr_inr === "number" ? `~${formatLakh(s.metrics.cost_to_own_5yr_inr)}` : NOT_STATED),
  },
  { label: "Range", cell: (s) => s.metrics.range_display ?? NOT_STATED },
  { label: "Efficiency", cell: (s) => s.metrics.efficiency_display ?? NOT_STATED },
  {
    label: "Running cost",
    cell: (s) => (typeof s.metrics.running_cost_inr_per_km === "number" ? `₹${s.metrics.running_cost_inr_per_km.toFixed(2)}/km` : NOT_STATED),
  },
  { label: "Crash test (adult)", cell: (s) => s.metrics.ncap_display ?? NOT_STATED },
  { label: "Home charger", cell: (s) => s.metrics.charger_note ?? NOT_STATED },
  {
    label: "DC fast charging",
    cell: (s) => s.metrics.dc_display ?? NOT_STATED,
  },
  { label: "Seats", cell: (s) => (s.metrics.seats != null ? String(s.metrics.seats) : NOT_STATED) },
  { label: "Boot", cell: (s) => (s.metrics.boot_l != null ? `${s.metrics.boot_l} L` : NOT_STATED) },
];

export default function SideBySide({ slots }: { slots: Slot[] }) {
  if (slots.length < 2) return null;
  return (
    <section aria-label="Side-by-side comparison" className="no-break flex flex-col gap-3.5 rounded-[18px] border border-line bg-white p-5 md:p-6">
      <h2 className="m-0 text-xl font-extrabold">Side by side</h2>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] border-collapse text-sm">
          <thead>
            <tr className="text-left text-muted">
              <th className="border-b-2 border-line p-2.5" />
              {slots.map((s, i) => (
                <th
                  key={s.variant_key}
                  className={`border-b-2 p-2.5 align-bottom font-bold ${i === 0 ? "border-brand text-ink" : "border-line"}`}
                >
                  {carName(s.metrics, s.variant_key)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="font-mono">
            {ROWS.map((row) => (
              <tr key={row.label}>
                <th scope="row" className="border-b border-chip p-2.5 text-left font-sans font-bold">
                  {row.label}
                </th>
                {slots.map((s) => (
                  <td key={s.variant_key} className="border-b border-chip p-2.5 align-top">
                    {row.cell(s)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
