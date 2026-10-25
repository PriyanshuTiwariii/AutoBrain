import { carName, formatLakh } from "@/lib/format";
import type { Result, Slot } from "@/lib/types";
import FeedbackLink from "./FeedbackLink";
import SideBySide from "./SideBySide";
import SlotCard from "./SlotCard";

const EYEBROW = "text-[13px] font-bold uppercase tracking-[0.08em] text-muted";

function NearMiss({ slot }: { slot: Slot }) {
  const m = slot.metrics;
  return (
    <div className="no-break flex flex-col gap-1.5">
      <div className="text-lg font-extrabold">
        {carName(m, slot.variant_key)}
        {slot.price_status !== "pending" && slot.price_inr > 0 ? ` · ${formatLakh(slot.price_inr)}` : ""}
      </div>
      <ul className="m-0 flex list-none flex-col gap-1 p-0">
        {slot.reasons.map((r, i) => (
          <li key={`${r.code}-${i}`} className="text-[15px] leading-relaxed">
            {r.detail ?? r.code}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The whole results page for one Result. Presentational: it only shows what the engine returned. */
export default function ResultView({ result, visitId }: { result: Result; visitId: string }) {
  const recommended = result.slots.filter((s) => s.slot !== "not_recommended");
  const nearMisses = result.slots.filter((s) => s.slot === "not_recommended");
  const best = recommended.find((s) => s.slot === "best_match");
  const others = recommended.filter((s) => s.slot === "same_model" || s.slot === "strong_alternative" || s.slot === "in_between");
  const dontOverpay = recommended.find((s) => s.slot === "dont_overpay");

  return (
    <main className="mx-auto flex max-w-[1180px] flex-col gap-6 px-5 pb-16 pt-8 md:gap-7 md:px-8 md:pt-9">
      <section aria-label="Your needs" className="flex flex-col gap-3.5">
        <div className={EYEBROW}>Your shortlist, based on what you told us</div>
        {best ? (
          <h1 className="m-0 text-2xl font-extrabold leading-tight tracking-tight md:text-4xl">
            {carName(best.metrics, best.variant_key)} is the {(best.metrics.relative_label ?? "strongest fit").toLowerCase()} for what you told us.
          </h1>
        ) : (
          <h1 className="m-0 text-2xl font-extrabold leading-tight tracking-tight md:text-4xl">
            Nothing in our data meets all your needs.
          </h1>
        )}
        <div className="flex flex-wrap gap-2">
          {result.needs_summary.map((line) => (
            <span key={line} className="rounded-full border border-line bg-white px-3.5 py-2 text-sm font-semibold">
              {line}
            </span>
          ))}
        </div>
      </section>

      {!best ? (
        <section className="rounded-[18px] border border-warn-line bg-warn-bg p-5">
          <p className="m-0 text-base leading-relaxed text-warn-ink">
            {result.unknowns[0] ?? "None of the vehicles in our current dataset meet all your requirements."}
          </p>
          {nearMisses.length > 0 ? (
            <p className="mb-0 mt-2 text-base text-warn-ink">The closest options are listed below. Loosening one need may help.</p>
          ) : null}
        </section>
      ) : null}

      {best ? <SlotCard slot={best} featured /> : null}

      {others.length > 0 ? (
        <section aria-label="Other good options" className="grid gap-5 md:grid-cols-2">
          {others.map((s) => (
            <SlotCard key={s.variant_key} slot={s} />
          ))}
        </section>
      ) : null}

      {dontOverpay ? <SlotCard slot={dontOverpay} /> : null}

      <SideBySide slots={recommended} />

      {nearMisses.length > 0 ? (
        <section aria-label="Considered, not recommended" className="no-break flex flex-col gap-4 rounded-[18px] bg-[#E9EDEF] p-5 md:px-6 md:py-[22px]">
          <div className="text-xs font-extrabold uppercase tracking-[0.08em] text-muted">Considered, not recommended for you</div>
          {nearMisses.map((s) => (
            <NearMiss key={s.variant_key} slot={s} />
          ))}
        </section>
      ) : null}

      {result.unknowns.length > 0 && best ? (
        <section aria-label="What we could not confirm" className="no-break flex flex-col gap-2 rounded-[14px] border border-line bg-white p-5">
          <h2 className="m-0 text-[15px] font-extrabold">What we could not confirm</h2>
          <ul className="m-0 flex list-disc flex-col gap-1 pl-5">
            {result.unknowns.map((u) => (
              <li key={u} className="text-sm leading-relaxed text-[#33424D]">
                {u}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section aria-label="How to read this" className="grid gap-4 md:grid-cols-3">
        <div className="no-break flex flex-col gap-1.5 rounded-[14px] border border-line bg-white p-[18px]">
          <h3 className="m-0 text-[15px] font-extrabold">Fit labels</h3>
          <p className="m-0 text-sm leading-relaxed text-[#33424D]">
            &ldquo;Strongest fit&rdquo; and &ldquo;Close second&rdquo; compare these cars for you. They compare cars for you; they are not a percentage score.
          </p>
        </div>
        <div className="no-break flex flex-col gap-1.5 rounded-[14px] border border-line bg-white p-[18px]">
          <h3 className="m-0 text-[15px] font-extrabold">Data confidence</h3>
          <p className="m-0 text-sm leading-relaxed text-[#33424D]">
            High when the price is official, range and efficiency were independently tested on this exact version, and the crash
            rating covers it.
          </p>
        </div>
        <div className="no-break flex flex-col gap-1.5 rounded-[14px] border border-line bg-white p-[18px]">
          <h3 className="m-0 text-[15px] font-extrabold">Before you buy</h3>
          <p className="m-0 text-sm leading-relaxed text-[#33424D]">
            Ask for an on-road quote and this month&rsquo;s offer. Costs marked ~ are estimates.
          </p>
        </div>
      </section>

      <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
        <FeedbackLink result={result} visitId={visitId} />
      </div>

      <footer className="flex flex-col gap-1.5 text-center text-[13px] text-muted">
        <p className="m-0">{result.disclaimer}</p>
        <p className="m-0">
          Data release {result.dataset_version} · engine {result.engine_version} · result {result.result_id}
        </p>
      </footer>
    </main>
  );
}
