"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import DescribeBox from "@/components/DescribeBox";
import Header from "@/components/Header";
import { applyExtraction } from "@/lib/extract";
import {
  EMPTY_FORM,
  FEATURES,
  HOME_CHARGING_OPTIONS,
  PRIORITIES,
  ROAD_CONDITIONS,
  buildNeeds,
  formFieldFor,
  type FormState,
} from "@/lib/needs";
import { getVisitId, loadForm, saveForm, saveResult } from "@/lib/storage";
import type { ExtractResponse, Feature, FieldProblem, Result } from "@/lib/types";

const INPUT =
  "min-h-12 w-full rounded-xl border border-[#A9B6BF] bg-white px-3.5 py-2.5 text-base text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/30";
const LABEL = "text-[15px] font-bold";
const HINT = "text-[13px] text-muted";

function Field({
  label, hint, error, children,
}: { label: string; hint?: string; error?: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className={LABEL}>{label}</label>
      {hint ? <div className={HINT}>{hint}</div> : null}
      {children}
      {error ? <div role="alert" className="text-sm font-semibold text-warn">{error}</div> : null}
    </div>
  );
}

function FeatureBoxes({
  legend, hint, selected, disabled, onToggle,
}: {
  legend: string; hint: string; selected: Feature[]; disabled: Feature[]; onToggle: (f: Feature) => void;
}) {
  return (
    <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
      <legend className={`${LABEL} mb-1 p-0`}>{legend}</legend>
      <div className={HINT}>{hint}</div>
      <div className="grid gap-2 sm:grid-cols-2">
        {FEATURES.map((f) => {
          const isOff = disabled.includes(f.value);
          return (
            <label
              key={f.value}
              className={`flex min-h-12 cursor-pointer items-center gap-3 rounded-xl border px-3.5 py-2.5 text-[15px] ${
                selected.includes(f.value) ? "border-brand bg-sky font-semibold" : "border-line bg-white"
              } ${isOff ? "cursor-not-allowed opacity-40" : ""}`}
            >
              <input
                type="checkbox"
                className="h-5 w-5 accent-brand"
                checked={selected.includes(f.value)}
                disabled={isOff}
                onChange={() => onToggle(f.value)}
              />
              {f.label}
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

export default function StartPage() {
  const router = useRouter();
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  // The answer can arrive seconds after the button was pressed: apply it to the form as it is now, not as it was then
  const latestForm = useRef(form);
  latestForm.current = form;
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Bring back what the buyer typed before (e.g. coming from "Edit my needs"); also starts this visit's random ID
  useEffect(() => {
    getVisitId();
    setForm(loadForm());
  }, []);

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((f) => ({ ...f, [key]: value }));
    setErrors((e) => ({ ...e, [key]: "" }));
  };

  const toggle = (key: "mustHaves" | "niceToHaves", feature: Feature) => {
    setForm((f) => {
      const has = f[key].includes(feature);
      return { ...f, [key]: has ? f[key].filter((x) => x !== feature) : [...f[key], feature] };
    });
  };

  // "Describe what you need" only fills the form in; nothing is submitted until the buyer presses the button
  const applyDescription = (response: ExtractResponse) => {
    const applied = applyExtraction(latestForm.current, response);
    latestForm.current = applied.form;
    setForm(applied.form);
    setErrors({});
    setFormError(null);
    return applied;
  };

  const showProblems = (problems: FieldProblem[]) => {
    const byField: Record<string, string> = {};
    const general: string[] = [];
    for (const p of problems) {
      const target = formFieldFor(p.field);
      if (target === "form") general.push(p.message);
      else byField[target] = byField[target] ? `${byField[target]} ${p.message}` : p.message;
    }
    setErrors(byField);
    // The field messages can be scrolled out of sight above the button, so say it here too
    const summary = [...general, ...Object.values(byField)];
    setFormError(summary.length ? summary.join(" ") : null);
  };

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setFormError(null);
    const { needs, problems } = buildNeeds(form);
    if (!needs) {
      showProblems(problems);
      return;
    }
    setErrors({});
    setBusy(true);
    saveForm(form);
    try {
      const response = await fetch("/api/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(needs),
      });
      const body: unknown = await response.json().catch(() => null);
      if (response.ok && body && typeof body === "object" && "slots" in body) {
        saveResult(body as Result);
        router.push("/r");
        return;
      }
      const detail = (body as { detail?: FieldProblem[] } | null)?.detail;
      if (Array.isArray(detail) && detail.length) showProblems(detail);
      else setFormError("Something went wrong. Please try again.");
    } catch {
      setFormError("We could not reach the server. Check your connection and try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Header />
      <main className="mx-auto max-w-[720px] px-5 pb-20 pt-8 md:px-8 md:pt-12">
        <Link href="/find" className="mb-4 inline-block text-[15px] font-bold">
          ← Back to the simple questions
        </Link>
        <h1 className="m-0 mb-2 text-[28px] font-extrabold tracking-tight md:text-4xl">All options</h1>
        <p className="m-0 mb-8 text-base text-muted">For people who know cars. Answer what you can. We only recommend cars the data can back up.</p>

        <DescribeBox onApply={applyDescription} />

        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-7">
          <Field label="Budget (₹ lakh)" hint="The most you want to spend, ex-showroom. For example 15 or 12.5." error={errors.budgetLakh}>
            <input
              className={INPUT}
              inputMode="decimal"
              placeholder="15"
              value={form.budgetLakh}
              onChange={(e) => set("budgetLakh", e.target.value)}
              aria-label="Budget in lakh rupees"
            />
          </Field>

          <Field label="Seats" hint="The fewest seats you need." error={errors.seats}>
            <select className={INPUT} value={form.seats} onChange={(e) => set("seats", e.target.value)} aria-label="Seats needed">
              {[2, 3, 4, 5, 6, 7].map((n) => (
                <option key={n} value={n}>{n} or more</option>
              ))}
            </select>
          </Field>

          <Field label="Daily driving (km)" hint="A typical day." error={errors.dailyKm}>
            <input
              className={INPUT}
              inputMode="numeric"
              placeholder="40"
              value={form.dailyKm}
              onChange={(e) => set("dailyKm", e.target.value)}
              aria-label="Daily driving in km"
            />
          </Field>

          <Field label="Longest regular trip (km), optional" hint="One way, for a trip you do regularly. Leave empty if you have none." error={errors.tripKm}>
            <input
              className={INPUT}
              inputMode="numeric"
              placeholder="e.g. 300"
              value={form.tripKm}
              onChange={(e) => set("tripKm", e.target.value)}
              aria-label="Longest regular trip in km"
            />
          </Field>

          <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
            <legend className={`${LABEL} mb-1 p-0`}>Can you charge at home?</legend>
            <div className="grid gap-2 sm:grid-cols-3">
              {HOME_CHARGING_OPTIONS.map((o) => (
                <label
                  key={o.value}
                  className={`flex min-h-12 cursor-pointer flex-col justify-center rounded-xl border px-3.5 py-2.5 ${
                    form.homeCharging === o.value ? "border-brand bg-sky" : "border-line bg-white"
                  }`}
                >
                  <span className="flex items-center gap-3 text-[15px] font-semibold">
                    <input
                      type="radio"
                      name="homeCharging"
                      className="h-5 w-5 accent-brand"
                      checked={form.homeCharging === o.value}
                      onChange={() => set("homeCharging", o.value)}
                    />
                    {o.label}
                  </span>
                  <span className="pl-8 text-[13px] text-muted">{o.hint}</span>
                </label>
              ))}
            </div>
            {errors.homeCharging ? <div role="alert" className="text-sm font-semibold text-warn">{errors.homeCharging}</div> : null}
          </fieldset>

          <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
            <legend className={`${LABEL} mb-1 p-0`}>What roads do you drive on?</legend>
            <div className={HINT}>We rank cars with higher stated ground clearance (and all-wheel drive for light off-road) higher. We never rule a car out for this.</div>
            <div className="grid gap-2 sm:grid-cols-3">
              {ROAD_CONDITIONS.map((o) => (
                <label
                  key={o.value}
                  className={`flex min-h-12 cursor-pointer flex-col justify-center rounded-xl border px-3.5 py-2.5 ${
                    form.roadConditions === o.value ? "border-brand bg-sky" : "border-line bg-white"
                  }`}
                >
                  <span className="flex items-center gap-3 text-[15px] font-semibold">
                    <input
                      type="radio"
                      name="roadConditions"
                      className="h-5 w-5 accent-brand"
                      checked={form.roadConditions === o.value}
                      onChange={() => set("roadConditions", o.value)}
                    />
                    {o.label}
                  </span>
                  <span className="pl-8 text-[13px] text-muted">{o.hint}</span>
                </label>
              ))}
            </div>
          </fieldset>

          <FeatureBoxes
            legend="Must-haves"
            hint="We will only show cars that have these."
            selected={form.mustHaves}
            disabled={form.niceToHaves}
            onToggle={(f) => toggle("mustHaves", f)}
          />
          <FeatureBoxes
            legend="Nice-to-haves"
            hint="A bonus if a car has them. We will not rule a car out for lacking them."
            selected={form.niceToHaves}
            disabled={form.mustHaves}
            onToggle={(f) => toggle("niceToHaves", f)}
          />

          <Field label="What matters most?" error={errors.priority}>
            <select
              className={INPUT}
              value={form.priority}
              onChange={(e) => set("priority", e.target.value as FormState["priority"])}
              aria-label="Priority"
            >
              {PRIORITIES.map((p) => (
                <option key={p.value} value={p.value}>{p.label}: {p.hint}</option>
              ))}
            </select>
          </Field>

          {formError ? (
            <div role="alert" className="rounded-xl border border-warn-line bg-warn-bg p-4 text-[15px] font-semibold text-warn-ink">
              {formError}
            </div>
          ) : null}

          <button
            type="submit"
            disabled={busy}
            aria-busy={busy}
            className="btn btn-primary"
          >
            {busy ? "Finding your shortlist…" : "Show my shortlist"}
          </button>
        </form>
      </main>
    </>
  );
}
