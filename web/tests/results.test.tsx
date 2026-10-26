import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import ResultView from "@/components/ResultView";
import { PRICE_STATUS_LABEL, carName, formatLakh } from "@/lib/format";
import type { Result } from "@/lib/types";
import { FIXTURES, fixture } from "./helpers";

function render(result: Result): string {
  return renderToStaticMarkup(<ResultView result={result} visitId="visit-test-0001" />);
}

/** The visible text of the page: tags and attributes gone, entities decoded, spaces collapsed. */
function textOf(html: string): string {
  return html
    .replace(/<[^>]*>/g, " ")
    .replace(/&#x27;|&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/\s+/g, " ");
}

/** Every number in the Result, written every way the page may write it. */
function allowedNumbers(result: Result): Set<string> {
  const allowed = new Set<string>();
  const addNumber = (n: number) => {
    for (const s of [String(n), n.toFixed(2), String(n / 100_000), (n / 100_000).toFixed(2), String(Math.round(n))]) allowed.add(s);
    allowed.add(n.toLocaleString("en-IN").replace(/,/g, ""));
  };
  const walk = (value: unknown) => {
    if (typeof value === "number") addNumber(value);
    else if (typeof value === "string") for (const m of value.matchAll(/\d+(?:[.,]\d+)*/g)) allowed.add(m[0].replace(/,/g, ""));
    else if (Array.isArray(value)) value.forEach(walk);
    else if (value && typeof value === "object") Object.values(value).forEach(walk);
  };
  walk(result);
  return allowed;
}

describe.each(FIXTURES)("results page for %s", (name) => {
  const result = fixture(name);
  const html = render(result);
  const text = textOf(html);

  it("shows every slot the engine returned, by name", () => {
    for (const slot of result.slots) {
      expect(text).toContain(carName(slot.metrics, slot.variant_key));
    }
  });

  it("shows every reason, trade-off, watch-out and unknown the engine returned", () => {
    for (const slot of result.slots) {
      for (const r of [...slot.reasons, ...slot.tradeoffs]) expect(text).toContain(r.detail ?? r.code);
      for (const w of slot.watch_outs) expect(text).toContain(w);
    }
    if (result.slots.length > 0) for (const u of result.unknowns) expect(text).toContain(u);
  });

  it("shows why nothing qualifies, the closest option and what it would take, when the engine says so", () => {
    for (const line of [...(result.no_match?.reasons ?? []), ...(result.no_match?.what_it_would_take ?? [])]) {
      expect(text).toContain(line);
    }
  });

  it("shows the disclaimer and the release", () => {
    expect(text).toContain(result.disclaimer);
    expect(text).toContain(result.dataset_version);
    expect(text).toContain(result.engine_version);
  });

  it("labels each price with its status, right next to it", () => {
    for (const slot of result.slots.filter((s) => s.slot !== "not_recommended")) {
      expect(text).toContain(PRICE_STATUS_LABEL[slot.price_status]);
      if (slot.price_status !== "pending") expect(text).toContain(formatLakh(slot.price_inr));
    }
  });

  it("has no percentage match ring", () => {
    expect(text).not.toMatch(/\d\s*%\s*match/i);
    expect(html).not.toContain("<circle");
    expect(html).not.toMatch(/aria-label="Match score/);
  });

  it("uses the engine's relative labels, only on cards that have one", () => {
    for (const label of ["Strongest fit", "Close second", "Third option", "Fourth option"]) {
      const expected = result.slots.filter((s) => s.metrics.relative_label === label).length;
      const shown = (html.match(new RegExp(`>${label}<`, "g")) ?? []).length;
      // The headline can repeat the best card's label in lower case, so count the badges only
      expect(shown).toBe(expected);
    }
    for (const slot of result.slots.filter((s) => s.slot === "in_between" || s.slot === "dont_overpay")) {
      expect(slot.metrics.relative_label ?? null).toBeNull();
    }
  });

  it("invents no numbers: every number shown comes from the Result", () => {
    const allowed = allowedNumbers(result);
    // "5-year" is a label, not a figure
    const shown = [...text.replace(/5-year/gi, " ").matchAll(/\d+(?:[.,]\d+)*/g)].map((m) => m[0].replace(/,/g, ""));
    const invented = shown.filter((n) => !allowed.has(n));
    expect(invented).toEqual([]);
  });

  it("never hides what the maker did not state", () => {
    expect(text).not.toMatch(/\bnull\b|\bundefined\b|NaN/);
  });
});

describe("results page details", () => {
  it("scenario 1: the earlier-version test is labelled with its note", () => {
    const result = fixture("scenario-1");
    const alt = result.slots.find((s) => s.slot === "strong_alternative");
    expect(alt?.metrics.range_display).toContain("tested on an earlier version");
    const text = textOf(render(result));
    expect(text).toContain("tested on an earlier version");
    expect(text).toContain(String(alt?.metrics.range_test_note));
    expect(text).not.toMatch(/187 km \(independent test\)/);
  });

  it("scenario 1: crash scores carry their status label, exactly as published", () => {
    const text = textOf(render(fixture("scenario-1")));
    expect(text).toContain("31.09/32 adult (Bharat NCAP, covers this version)");
    expect(text).toContain("No Bharat NCAP crash test for this EV");
  });

  it("scenario 6: says plainly that nothing qualifies, why, the closest option and what it would take", () => {
    const result = fixture("scenario-6-nothing-qualifies");
    const html = render(result);
    const text = textOf(html);
    expect(text).toContain("Nothing in our data meets all your needs.");
    expect(text).toContain("None of the vehicles in our current dataset meet all your requirements.");
    expect(text).toContain("Why nothing qualifies");
    expect(text).toContain("No variant within ₹8 lakh has 7 seats.");
    expect(text).toContain("No variant within ₹8 lakh is confirmed to have AWD (not stated by the maker for Tata Tiago.ev Smart 19).");
    expect(text).toContain("The closest option");
    expect(text).toContain("Tata Tiago.ev Smart 19");
    expect(text).toContain("What it would take to get that option");
    expect(text).toContain("Accept 5 seats; you asked for 7.");
    expect(text).toContain("Confirm with the maker: AWD is not stated for this variant.");
    // the closest option is a plain block, not a recommendation card
    expect(html).not.toContain("<article");
    // no dangling promise
    expect(text).not.toContain("Here's why");
    // and not shown a second time as a "considered, not recommended" box
    expect(text).not.toContain("Considered, not recommended for you");
  });

  it("the fit-label note appears only when there are fit labels to explain", () => {
    expect(textOf(render(fixture("scenario-1")))).toContain("They are not a percentage score.");
    expect(textOf(render(fixture("scenario-1")))).not.toContain("compare cars for you");
    expect(textOf(render(fixture("scenario-6-nothing-qualifies")))).not.toContain("Fit labels");
  });

  it("when matches exist the page has no nothing-qualifies section", () => {
    const text = textOf(render(fixture("scenario-1")));
    expect(text).not.toContain("Why nothing qualifies");
    expect(text).toContain("Considered, not recommended for you");
  });

  it("scenario 5: a side-by-side table compares the recommended cars", () => {
    const html = render(fixture("scenario-5"));
    expect(html).toContain("<table");
    expect(textOf(html)).toContain("Side by side");
  });

  it("the feedback link is explained, not hidden, when no form is set up", () => {
    expect(textOf(render(fixture("scenario-1")))).toContain("NEXT_PUBLIC_FEEDBACK_FORM_URL");
  });
});
