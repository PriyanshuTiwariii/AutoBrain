"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import CompareView from "@/components/CompareView";
import Header from "@/components/Header";
import PrintButton from "@/components/PrintButton";
import {
  MAX_CARS, MIN_CARS, brandsOf, compareHref, isCarsResponse, isCompareResponse, modelsOf, parseCarsParam, variantLabel,
  variantsOf,
} from "@/lib/compare";
import type { CarOption, CompareResponse, FieldProblem } from "@/lib/types";

const SELECT =
  "min-h-12 w-full rounded-xl border border-[#A9B6BF] bg-white px-3.5 py-2.5 text-base text-ink focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/30 disabled:bg-surface disabled:text-muted";

interface Pick {
  brand: string;
  model: string;
  key: string;
}
const EMPTY: Pick = { brand: "", model: "", key: "" };

function CarPicker({
  index, cars, includeBaas, value, onChange, onRemove,
}: {
  index: number;
  cars: CarOption[];
  includeBaas: boolean;
  value: Pick;
  onChange: (next: Pick) => void;
  onRemove?: () => void;
}) {
  const brands = brandsOf(cars, includeBaas);
  const models = value.brand ? modelsOf(cars, value.brand, includeBaas) : [];
  const variants = value.brand && value.model ? variantsOf(cars, value.brand, value.model, includeBaas) : [];
  return (
    <fieldset className="m-0 flex flex-col gap-2 rounded-2xl border border-line bg-white p-4">
      <legend className="px-1 text-[15px] font-extrabold">Car {index + 1}</legend>
      <select className={SELECT} aria-label={`Car ${index + 1} brand`} value={value.brand} onChange={(e) => onChange({ brand: e.target.value, model: "", key: "" })}>
        <option value="">Choose a brand</option>
        {brands.map((b) => (
          <option key={b} value={b}>{b}</option>
        ))}
      </select>
      <select
        className={SELECT}
        aria-label={`Car ${index + 1} model`}
        value={value.model}
        disabled={!value.brand}
        onChange={(e) => onChange({ ...value, model: e.target.value, key: "" })}
      >
        <option value="">Choose a model</option>
        {models.map((m) => (
          <option key={m} value={m}>{m}</option>
        ))}
      </select>
      <select
        className={SELECT}
        aria-label={`Car ${index + 1} variant`}
        value={value.key}
        disabled={!value.model}
        onChange={(e) => onChange({ ...value, key: e.target.value })}
      >
        <option value="">Choose a variant</option>
        {variants.map((v) => (
          <option key={v.variant_key} value={v.variant_key}>{variantLabel(v)}</option>
        ))}
      </select>
      {onRemove ? (
        <button type="button" onClick={onRemove} className="chip-btn self-start rounded-full px-3 py-1.5 text-[13px] font-bold text-brand">
          Remove this car
        </button>
      ) : null}
    </fieldset>
  );
}

export default function ComparePage() {
  const [cars, setCars] = useState<CarOption[]>([]);
  const [loadingCars, setLoadingCars] = useState(true);
  const [picks, setPicks] = useState<Pick[]>([EMPTY, EMPTY]);
  const [includeBaas, setIncludeBaas] = useState(false);
  const [data, setData] = useState<CompareResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);
  const resultRef = useRef<HTMLDivElement>(null);

  const chosenKeys = picks.map((p) => p.key).filter(Boolean);
  const canCompare = chosenKeys.length >= MIN_CARS && chosenKeys.length === picks.length && new Set(chosenKeys).size === chosenKeys.length;
  const sameCar = chosenKeys.length !== new Set(chosenKeys).size;

  async function compare(keys: string[]) {
    setBusy(true);
    setError(null);
    try {
      const reply = await fetch("/api/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ variant_keys: keys }),
      });
      const body: unknown = await reply.json().catch(() => null);
      if (reply.ok && isCompareResponse(body)) {
        setData(body);
        window.history.replaceState(null, "", compareHref(keys));
        setTimeout(() => resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
      } else {
        const detail = (body as { detail?: FieldProblem[] } | null)?.detail;
        setError(Array.isArray(detail) && detail.length ? detail.map((p) => p.message).join(" ") : "Something went wrong. Please try again.");
      }
    } catch {
      setError("We could not reach the server. Check your connection and try again.");
    } finally {
      setBusy(false);
    }
  }

  // Load the list of cars; if the link carries cars (?cars=a,b), pre-select them and compare straight away
  useEffect(() => {
    let live = true;
    (async () => {
      try {
        const reply = await fetch("/api/cars");
        const body: unknown = await reply.json().catch(() => null);
        if (!live) return;
        if (!reply.ok || !isCarsResponse(body)) {
          setError("We could not load the list of cars. Please try again in a moment.");
          return;
        }
        setCars(body.cars);
        const keys = parseCarsParam(new URLSearchParams(window.location.search).get("cars"));
        const found = keys.map((k) => body.cars.find((c) => c.variant_key === k)).filter((c): c is CarOption => !!c);
        if (found.length >= MIN_CARS) {
          setIncludeBaas(found.some((c) => c.pricing_type === "BaaS"));
          setPicks(found.map((c) => ({ brand: c.brand, model: c.model, key: c.variant_key })));
          void compare(found.map((c) => c.variant_key));
        }
      } catch {
        if (live) setError("We could not reach the server. Check your connection and try again.");
      } finally {
        if (live) setLoadingCars(false);
      }
    })();
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setPick = (i: number, next: Pick) => setPicks((p) => p.map((x, j) => (j === i ? next : x)));
  const hasBaas = useMemo(() => cars.some((c) => c.pricing_type === "BaaS"), [cars]);

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(`${window.location.origin}${compareHref(chosenKeys)}`);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("Could not copy the link. You can copy it from the address bar.");
    }
  }

  return (
    <>
      <Header>
        <Link href="/find" className="btn btn-ghost !rounded-[10px]">
          Find a car instead
        </Link>
      </Header>
      <main className="mx-auto max-w-[960px] px-5 pb-24 pt-8 md:px-8 md:pt-12">
        <Link href="/start/ev" className="mb-4 inline-block text-[15px] font-bold print:hidden">
          &larr; Back
        </Link>
        <h1 className="m-0 mb-2 text-[28px] font-extrabold tracking-tight md:text-4xl">Compare electric cars</h1>
        <p className="m-0 mb-6 max-w-[640px] text-base text-muted">
          Pick two or three cars you are considering. We show them side by side, straight from our data, and where each one leads. We do not
          pick an overall winner.
        </p>

        <section aria-label="Choose cars" className="flex flex-col gap-4 print:hidden">
          <div className={`grid gap-3 ${picks.length === 3 ? "md:grid-cols-3" : "md:grid-cols-2"}`}>
            {picks.map((p, i) => (
              <CarPicker
                key={i}
                index={i}
                cars={cars}
                includeBaas={includeBaas}
                value={p}
                onChange={(next) => setPick(i, next)}
                onRemove={picks.length > MIN_CARS && i === picks.length - 1 ? () => setPicks((all) => all.slice(0, -1)) : undefined}
              />
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {picks.length < MAX_CARS ? (
              <button type="button" onClick={() => setPicks((all) => [...all, EMPTY])} className="btn btn-light">
                + Add a third car
              </button>
            ) : null}
            {hasBaas ? (
              <label className="flex min-h-12 cursor-pointer items-center gap-2.5 text-[15px]">
                <input
                  type="checkbox"
                  className="h-5 w-5 accent-brand"
                  checked={includeBaas}
                  onChange={(e) => {
                    setIncludeBaas(e.target.checked);
                    if (!e.target.checked) setPicks((all) => all.map((p) => (cars.find((c) => c.variant_key === p.key)?.pricing_type === "BaaS" ? EMPTY : p)));
                  }}
                />
                Include versions with battery rental (BaaS)
              </label>
            ) : null}
          </div>

          {sameCar ? (
            <div role="alert" className="rounded-xl border border-warn-line bg-warn-bg p-3.5 text-[15px] font-semibold text-warn-ink">
              You picked the same car twice. Choose two different cars.
            </div>
          ) : null}
          {error ? (
            <div role="alert" className="rounded-xl border border-warn-line bg-warn-bg p-3.5 text-[15px] font-semibold text-warn-ink">
              {error}
            </div>
          ) : null}

          <div className="sticky-cta flex flex-col gap-2 sm:flex-row sm:items-center">
            <button
              type="button"
              onClick={() => void compare(chosenKeys)}
              disabled={!canCompare || busy || loadingCars}
              aria-busy={busy || loadingCars}
              className="btn btn-primary w-full shadow-lg sm:w-auto"
            >
              {loadingCars ? "Loading cars…" : busy ? "Comparing…" : "Compare these cars"}
            </button>
          </div>
        </section>

        <div ref={resultRef} className="mt-8 scroll-mt-4">
          {data ? (
            <>
              <div className="mb-4 flex flex-wrap items-center gap-3 print:hidden">
                <PrintButton className="btn btn-light" />
                <button type="button" onClick={copyLink} className="btn btn-secondary">
                  {copied ? "Link copied" : "Copy link to this comparison"}
                </button>
              </div>
              <CompareView data={data} />
            </>
          ) : null}
        </div>
      </main>
    </>
  );
}
