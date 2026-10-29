"use client";

import { useState } from "react";
import { COMMUTE_ASSUMPTIONS, EMI_ASSUMPTIONS, budgetFromEmi, dailyKmFromCommuteMinutes, loanFromEmi } from "@/lib/guided";
import { lakhText } from "@/lib/extract";

const INPUT =
  "min-h-12 w-full rounded-xl border border-[#A9B6BF] bg-white px-3.5 py-2.5 text-base text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/30";
const USE_BUTTON = "btn btn-primary";

function number(text: string): number {
  return text.trim() === "" ? Number.NaN : Number(text.replace(/,/g, ""));
}

/** "Help me decide": a monthly EMI and a down payment become a suggested budget. The buyer confirms it. */
export function BudgetHelper({ onUse }: { onUse: (inr: number) => void }) {
  const [emi, setEmi] = useState("");
  const [years, setYears] = useState("5");
  const [down, setDown] = useState("");
  const [rate, setRate] = useState(String(EMI_ASSUMPTIONS.annualRatePercent));
  const downInr = down.trim() === "" ? 0 : number(down) * 100_000;
  const loan = loanFromEmi(number(emi), Number(years), number(rate));
  const budget = budgetFromEmi(number(emi), Number(years), downInr, number(rate));

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-sky-line bg-sky p-4" aria-label="Budget helper">
      <label className="flex flex-col gap-1.5 text-[15px] font-bold">
        Monthly EMI you are comfortable paying (₹)
        <input className={INPUT} inputMode="numeric" placeholder="20000" value={emi} onChange={(e) => setEmi(e.target.value)} />
      </label>
      <label className="flex flex-col gap-1.5 text-[15px] font-bold">
        Loan length
        <select className={INPUT} value={years} onChange={(e) => setYears(e.target.value)}>
          {[3, 5, 7].map((y) => (
            <option key={y} value={y}>{y} years</option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1.5 text-[15px] font-bold">
        Down payment you can give now (₹ lakh), optional
        <input className={INPUT} inputMode="decimal" placeholder="2" value={down} onChange={(e) => setDown(e.target.value)} />
      </label>
      <label className="flex flex-col gap-1.5 text-[15px] font-bold">
        Interest rate a year (%), change it to your bank&apos;s rate
        <input className={INPUT} inputMode="decimal" value={rate} onChange={(e) => setRate(e.target.value)} />
      </label>
      <p className="m-0 text-[13px] text-muted">
        This is an estimate, not a loan offer. The rate starts at {EMI_ASSUMPTIONS.annualRatePercent}% as a guess; your bank&apos;s rate depends on
        you and the lender. We round down to the nearest ₹50,000.
      </p>
      {budget !== null && loan !== null ? (
        <div className="flex flex-col gap-2">
          <p className="m-0 text-[15px] font-bold">
            An EMI of ₹{Math.round(number(emi)).toLocaleString("en-IN")} for {years} years at {number(rate)}% repays a loan of about{" "}
            {lakhText(Math.round(loan))} lakh. With your down payment, that is a budget of about {lakhText(budget)} lakh.
          </p>
          <button type="button" className={USE_BUTTON} onClick={() => onUse(budget)}>
            Use up to {lakhText(budget)} lakh
          </button>
        </div>
      ) : (
        <p className="m-0 text-[13px] text-muted">Fill in the EMI to see a budget.</p>
      )}
    </div>
  );
}

/** "Not sure how far": minutes of travel one way become a daily distance. The buyer confirms it. */
export function CommuteHelper({ onUse }: { onUse: (km: number) => void }) {
  const [minutes, setMinutes] = useState("");
  const [speed, setSpeed] = useState(String(COMMUTE_ASSUMPTIONS.averageSpeedKmh));
  const km = dailyKmFromCommuteMinutes(number(minutes), number(speed));

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-sky-line bg-sky p-4" aria-label="Distance helper">
      <label className="flex flex-col gap-1.5 text-[15px] font-bold">
        How many minutes does it take to reach work, one way?
        <input className={INPUT} inputMode="numeric" placeholder="30" value={minutes} onChange={(e) => setMinutes(e.target.value)} />
      </label>
      <label className="flex flex-col gap-1.5 text-[15px] font-bold">
        Average speed on that trip (km/h), change it if your route is faster or slower
        <input className={INPUT} inputMode="numeric" value={speed} onChange={(e) => setSpeed(e.target.value)} />
      </label>
      <p className="m-0 text-[13px] text-muted">
        This is a rough estimate. The speed starts at {COMMUTE_ASSUMPTIONS.averageSpeedKmh} km/h as a guess for city traffic. We count the trip
        there and back and nothing else, so add extra if you also drive to other places most days.
      </p>
      {km !== null ? (
        <div className="flex flex-col gap-2">
          <p className="m-0 text-[15px] font-bold">{minutes} minutes one way at {number(speed)} km/h, there and back, is about {km} km a day.</p>
          <button type="button" className={USE_BUTTON} onClick={() => onUse(km)}>
            Use about {km} km a day
          </button>
        </div>
      ) : (
        <p className="m-0 text-[13px] text-muted">Fill in the minutes to see a distance.</p>
      )}
    </div>
  );
}
