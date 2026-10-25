import { describe, expect, it } from "vitest";
import { EMPTY_FORM, FEATURES, HOME_CHARGING_OPTIONS, LIMITS, PRIORITIES, buildNeeds, formFieldFor, type FormState } from "@/lib/needs";
import { contract } from "./helpers";

const valid: FormState = { ...EMPTY_FORM, budgetLakh: "15", dailyKm: "40", homeCharging: "yes" };

describe("buildNeeds", () => {
  it("turns lakh into rupees once, and passes the rest through", () => {
    const { needs, problems } = buildNeeds({ ...valid, priority: "safety", mustHaves: ["adas"], niceToHaves: ["sunroof"] });
    expect(problems).toEqual([]);
    expect(needs).toEqual({
      budget_max_inr: 1_500_000,
      seats_min: 5,
      daily_km: 40,
      home_charging: "yes",
      must_haves: ["adas"],
      nice_to_haves: ["sunroof"],
      priority: "safety",
    });
  });

  it.each([
    ["12.5", 1_250_000],
    ["10.1", 1_010_000],
    ["3", 300_000],
    [" 25 ", 2_500_000],
  ])("budget %s lakh → %i", (lakh, inr) => {
    expect(buildNeeds({ ...valid, budgetLakh: lakh }).needs?.budget_max_inr).toBe(inr);
  });

  it("includes the longest trip only when given", () => {
    expect(buildNeeds(valid).needs).not.toHaveProperty("longest_regular_trip_km");
    expect(buildNeeds({ ...valid, tripKm: "300" }).needs?.longest_regular_trip_km).toBe(300);
  });

  it("a must-have is never also sent as a nice-to-have", () => {
    const { needs } = buildNeeds({ ...valid, mustHaves: ["adas", "esp"], niceToHaves: ["esp", "sunroof"] });
    expect(needs?.nice_to_haves).toEqual(["sunroof"]);
  });

  it.each([
    [{ budgetLakh: "" }, "budgetLakh"],
    [{ budgetLakh: "lots" }, "budgetLakh"],
    [{ budgetLakh: "2.9" }, "budgetLakh"],
    [{ seats: "9" }, "seats"],
    [{ dailyKm: "" }, "dailyKm"],
    [{ dailyKm: "0" }, "dailyKm"],
    [{ dailyKm: "501" }, "dailyKm"],
    [{ dailyKm: "12.5" }, "dailyKm"],
    [{ tripKm: "far" }, "tripKm"],
    [{ tripKm: "0" }, "tripKm"],
    [{ homeCharging: "" as const }, "homeCharging"],
  ])("rejects %j with a message on %s", (change, field) => {
    const { needs, problems } = buildNeeds({ ...valid, ...change });
    expect(needs).toBeUndefined();
    expect(problems.map((p) => p.field)).toContain(field);
  });

  it("reports every problem at once", () => {
    const { problems } = buildNeeds({ ...EMPTY_FORM });
    expect(problems.map((p) => p.field).sort()).toEqual(["budgetLakh", "dailyKm", "homeCharging"]);
  });
});

describe("formFieldFor", () => {
  it("maps engine fields to form fields, including list items", () => {
    expect(formFieldFor("budget_max_inr")).toBe("budgetLakh");
    expect(formFieldFor("must_haves[1]")).toBe("mustHaves");
    expect(formFieldFor("longest_regular_trip_km")).toBe("tripKm");
    expect(formFieldFor("(server)")).toBe("form");
  });

  it("form fields map to themselves, so the form's own messages land under their inputs", () => {
    for (const field of ["budgetLakh", "seats", "dailyKm", "tripKm", "homeCharging"]) expect(formFieldFor(field)).toBe(field);
  });

  it("every problem buildNeeds can report lands on an input, not the general banner", () => {
    const { problems } = buildNeeds({ ...EMPTY_FORM, seats: "9", tripKm: "far" });
    expect(problems.length).toBeGreaterThanOrEqual(5);
    for (const p of problems) expect(formFieldFor(p.field)).not.toBe("form");
  });
});

describe("the form stays in step with contracts/needs.schema.json", () => {
  const props = contract("needs").properties;

  it("limits", () => {
    expect(LIMITS.budgetMinInr).toBe(props.budget_max_inr.minimum);
    expect(LIMITS.seatsMin).toBe(props.seats_min.minimum);
    expect(LIMITS.seatsMax).toBe(props.seats_min.maximum);
    expect(LIMITS.dailyKmMin).toBe(props.daily_km.minimum);
    expect(LIMITS.dailyKmMax).toBe(props.daily_km.maximum);
    expect(LIMITS.tripKmMin).toBe(props.longest_regular_trip_km.minimum);
  });

  it("features, priorities and home-charging options are exactly the contract's enums", () => {
    expect(FEATURES.map((f) => f.value).sort()).toEqual([...props.must_haves.items.enum].sort());
    expect(FEATURES.map((f) => f.value).sort()).toEqual([...props.nice_to_haves.items.enum].sort());
    expect(PRIORITIES.map((p) => p.value).sort()).toEqual([...props.priority.enum].sort());
    expect(HOME_CHARGING_OPTIONS.map((o) => o.value).sort()).toEqual([...props.home_charging.enum].sort());
  });

  it("the default priority is the contract's default", () => {
    expect(EMPTY_FORM.priority).toBe(props.priority.default);
  });
});
