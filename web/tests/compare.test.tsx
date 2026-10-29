import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import CompareView from "@/components/CompareView";
import {
  MAX_CARS, MIN_CARS, brandsOf, compareHref, isCarsResponse, isCompareResponse, modelsOf, parseCarsParam, variantLabel, variantsOf,
} from "@/lib/compare";
import type { CarOption } from "@/lib/types";
import { compareFixture, contract } from "./helpers";

const car = (over: Partial<CarOption>): CarOption => ({
  variant_key: "K", brand: "Tata", model: "Punch.ev", variant: "Smart", body_type: "SUV", pricing_type: "battery included",
  price_inr: 1_000_000, price_status: "verified", ...over,
});
const CARS: CarOption[] = [
  car({ variant_key: "T1", variant: "Smart", price_inr: 1_100_000 }),
  car({ variant_key: "T2", variant: "Empowered", price_inr: 1_400_000 }),
  car({ variant_key: "T3", model: "Nexon.ev", variant: "Creative" }),
  car({ variant_key: "M1", brand: "Mahindra", model: "XEV 9e", variant: "Pack Two" }),
  car({ variant_key: "M2", brand: "Mahindra", model: "XEV 9e", variant: "Pack Two BaaS", pricing_type: "BaaS", price_inr: null, price_status: "pending" }),
];

describe("engine fixtures", () => {
  it("are recognised as comparisons and match the contract's top-level fields", () => {
    const required = contract("compare.response").required as string[];
    for (const name of ["three", "baas"] as const) {
      const data = compareFixture(name);
      expect(isCompareResponse(data)).toBe(true);
      expect(Object.keys(data).sort()).toEqual([...required].sort());
    }
  });

  it("the request contract allows two or three cars, as the page does", () => {
    const schema = contract("compare.request").properties.variant_keys;
    expect([schema.minItems, schema.maxItems]).toEqual([MIN_CARS, MAX_CARS]);
  });

  it("rejects things that are not comparisons or car lists", () => {
    expect(isCompareResponse(null)).toBe(false);
    expect(isCompareResponse({ cars: [] })).toBe(false);
    const data = compareFixture("three");
    expect(isCompareResponse({ ...data, cars: data.cars.slice(0, 1) })).toBe(false);
    expect(isCompareResponse({ ...data, sections: [{ title: "x", rows: [{ label: "y", cells: [] }] }] })).toBe(false);
    expect(isCarsResponse({ dataset_version: "r", cars: [{ variant_key: 1 }] })).toBe(false);
    expect(isCarsResponse({ dataset_version: "r", cars: CARS })).toBe(true);
  });
});

describe("pickers", () => {
  it("hide battery-rental versions unless asked", () => {
    expect(variantsOf(CARS, "Mahindra", "XEV 9e", false).map((c) => c.variant_key)).toEqual(["M1"]);
    expect(variantsOf(CARS, "Mahindra", "XEV 9e", true).map((c) => c.variant_key)).toEqual(["M1", "M2"]);
  });

  it("list brands, models and variants, cheapest first, from the data only", () => {
    expect(brandsOf(CARS, false)).toEqual(["Mahindra", "Tata"]);
    expect(modelsOf(CARS, "Tata", false)).toEqual(["Nexon.ev", "Punch.ev"]);
    expect(variantsOf(CARS, "Tata", "Punch.ev", false).map((c) => c.variant_key)).toEqual(["T1", "T2"]);
    expect(modelsOf(CARS, "Nope", false)).toEqual([]);
  });

  it("label a variant with its price, or say the price is not confirmed", () => {
    expect(variantLabel(CARS[0]!)).toBe("Smart (₹11 lakh)");
    expect(variantLabel(CARS[4]!)).toBe("Pack Two BaaS (price not confirmed, battery rental)");
  });
});

describe("links", () => {
  it("round-trip the chosen cars, at most three, without repeats or odd characters", () => {
    expect(parseCarsParam(compareHref(["A-1", "B.2"]).split("=")[1])).toEqual(["A-1", "B.2"]);
    expect(parseCarsParam("a,a,b,c,d")).toEqual(["a", "b", "c"]);
    expect(parseCarsParam("a, <script>,b")).toEqual(["a", "b"]);
    expect(parseCarsParam(null)).toEqual([]);
    expect(compareHref([])).toBe("/compare");
  });
});

describe("CompareView", () => {
  const html = renderToStaticMarkup(<CompareView data={compareFixture("three")} />);

  it("shows every car's name and each section", () => {
    for (const car of compareFixture("three").cars) expect(html).toContain(car.name);
    for (const title of ["Price and cost", "Range and charging", "Safety", "Comfort and features", "Space and ground"]) {
      expect(html).toContain(title);
    }
  });

  it("shows where each car leads using the engine's wording, and marks the winning cells", () => {
    const data = compareFixture("three");
    for (const w of data.winners.filter((x) => x.variant_key)) expect(html).toContain(w.text.replace(/&/g, "&amp;"));
    expect(html.match(/Leads here/g)?.length).toBe(data.sections.flatMap((s) => s.rows).flatMap((r) => r.cells).filter((c) => c.best).length);
  });

  it("says plainly when there is no clear leader, and why", () => {
    const data = compareFixture("three");
    const none = data.winners.filter((w) => w.variant_key === null);
    expect(none.length).toBeGreaterThan(0);
    expect(html).toContain("No clear leader");
    for (const w of none) expect(html).toContain(w.text);
  });

  it("shows unknowns as 'Not stated by maker', never blank", () => {
    const data = compareFixture("three");
    const unknown = data.sections.flatMap((s) => s.rows).flatMap((r) => r.cells).filter((c) => c.state === "not_stated");
    for (const c of unknown) expect(c.text.length).toBeGreaterThan(0);
    if (unknown.some((c) => c.text === "Not stated by maker")) expect(html).toContain("Not stated by maker");
  });

  it("always shows watch-outs, the notes, the disclaimer and never an overall winner", () => {
    expect(html).toContain("Watch-outs");
    expect(html).toContain("do not pick an overall winner");
    expect(html).toContain("default assumptions");
    expect(html).toContain(compareFixture("three").disclaimer);
    expect(html.toLowerCase()).not.toContain("overall winner is");
    expect(html.toLowerCase()).not.toContain("best overall");
  });

  it("keeps price status next to the price", () => {
    expect(html).toMatch(/\(verified\)|\(corroborated\)/);
  });

  it("battery rental is never compared with a battery-included price", () => {
    const baas = renderToStaticMarkup(<CompareView data={compareFixture("baas")} />);
    expect(baas).toContain("battery rental");
    expect(baas).toContain("do not compare them");
    expect(baas).toContain("Not calculated for battery rental");
  });
});
