import { describe, expect, it } from "vitest";
import {
  EMI_ASSUMPTIONS, applyPatch, budgetFromEmi, chipsFor, dailyKmFromCommuteMinutes, formToPartial, isQuestionResponse, loanFromEmi,
  markAsked, mergeExtraction, removeField, toFormState, toRecommendNeeds,
} from "@/lib/guided";
import { LIMITS } from "@/lib/needs";
import { contract, extractFixture, questionFixture } from "./helpers";

const GATE = { budget_max_inr: 1_500_000, seats_min: 4, daily_km: 40 } as const;

describe("engine question fixtures", () => {
  it("are recognised and match the response contract's shape", () => {
    const schema = contract("questions.response");
    for (const q of [questionFixture("budget"), questionFixture("optional")]) {
      expect(isQuestionResponse(q)).toBe(true);
      expect(Object.keys(q).sort()).toEqual([...schema.required].sort());
    }
  });

  it("the first question is budget, with a helper and cards that set only that field", () => {
    const q = questionFixture("budget");
    expect(q).toMatchObject({ kind: "required", field: "budget_max_inr", helper: "budget_emi", can_show_results: false });
    for (const card of q.cards) expect(Object.keys(card.patch)).toEqual(["budget_max_inr"]);
  });

  it("rejects things that are not question responses", () => {
    expect(isQuestionResponse(null)).toBe(false);
    expect(isQuestionResponse({ done: true })).toBe(false);
    expect(isQuestionResponse({ ...questionFixture("budget"), cards: [{ id: 1 }] })).toBe(false);
  });
});

describe("applyPatch and answers", () => {
  it("a tapped card sets only what its patch says", () => {
    expect(applyPatch({ seats_min: 4 }, { budget_max_inr: 1_000_000 })).toEqual({ seats_min: 4, budget_max_inr: 1_000_000 });
  });

  it("skipping an optional question (empty patch) changes nothing", () => {
    expect(applyPatch({ ...GATE }, {})).toEqual({ ...GATE });
  });

  it("optional fields stay asked once answered or skipped; required fields are not tracked", () => {
    expect(markAsked([], "priority")).toEqual(["priority"]);
    expect(markAsked(["priority"], "priority")).toEqual(["priority"]);
    expect(markAsked([], "budget_max_inr")).toEqual([]);
    expect(markAsked([], null)).toEqual([]);
  });

  it("removing an answer forgets just that field", () => {
    expect(removeField({ ...GATE, priority: "safety" }, "priority")).toEqual({ ...GATE });
  });
});

describe("mergeExtraction", () => {
  it("adds what the engine read and keeps everything else", () => {
    const merged = mergeExtraction({ seats_min: 5 }, extractFixture("missing-budget"));
    expect(merged).toMatchObject({ seats_min: 4, home_charging: "yes" });
  });

  it("when answering one question, only that field is taken from typed words", () => {
    const merged = mergeExtraction({}, extractFixture("complete"), "seats_min");
    expect(merged).toEqual({ seats_min: 5 });
  });

  it("empty lists and fields the engine did not read leave known answers alone", () => {
    const merged = mergeExtraction({ ...GATE, must_haves: ["adas"] }, { ...extractFixture("off-topic"), needs: { must_haves: [] } });
    expect(merged).toEqual({ ...GATE, must_haves: ["adas"] });
  });

  it("ignores fields the page cannot use (pricing, body types, excluded models)", () => {
    const merged = mergeExtraction({}, extractFixture("complete"));
    expect(merged).not.toHaveProperty("exclude_models");
    expect(merged).not.toHaveProperty("body_types");
  });
});

describe("chips: what we understood, in plain words", () => {
  it("shows each known answer without jargon codes", () => {
    const chips = chipsFor({ ...GATE, home_charging: "unsure", road_conditions: "rough_roads", priority: "safety" });
    expect(chips.map((c) => c.value)).toEqual([
      "Up to 15 lakh", "4 or more", "About 40 km", "Home charging: not sure yet", "Potholes and speed breakers", "Keeping my family safe",
    ]);
  });

  it("shows nothing for unknown fields", () => {
    expect(chipsFor({})).toEqual([]);
  });

  it("names features by their labels", () => {
    const chips = chipsFor({ must_haves: ["adas"], nice_to_haves: ["sunroof"] });
    expect(chips.map((c) => c.label)).toEqual(["Must have", "Would like"]);
  });
});

describe("toRecommendNeeds", () => {
  it("never fills in budget, seats or daily km", () => {
    for (const missing of ["budget_max_inr", "seats_min", "daily_km"] as const) {
      const known = removeField({ ...GATE }, missing);
      const { needs, problems } = toRecommendNeeds(known);
      expect(needs).toBeUndefined();
      expect(problems.map((p) => p.field)).toEqual([missing]);
    }
  });

  it("home charging not yet answered becomes 'unsure', never yes or no", () => {
    expect(toRecommendNeeds({ ...GATE }).needs?.home_charging).toBe("unsure");
    expect(toRecommendNeeds({ ...GATE, home_charging: "no" }).needs?.home_charging).toBe("no");
  });

  it("builds the same Needs the form builds, and no must-haves unless the buyer asked", () => {
    const { needs } = toRecommendNeeds({ ...GATE, home_charging: "yes", priority: "cost", road_conditions: "rough_roads" });
    expect(needs).toEqual({
      budget_max_inr: 1_500_000, seats_min: 4, daily_km: 40, home_charging: "yes",
      must_haves: [], nice_to_haves: [], priority: "cost", road_conditions: "rough_roads",
    });
  });

  it("sends the long trip only when answered", () => {
    expect(toRecommendNeeds({ ...GATE }).needs).not.toHaveProperty("longest_regular_trip_km");
    expect(toRecommendNeeds({ ...GATE, longest_regular_trip_km: 300 }).needs?.longest_regular_trip_km).toBe(300);
  });

  it("every card patch the engine offers produces valid Needs together with the gate answers", () => {
    for (const q of [questionFixture("budget"), questionFixture("optional")]) {
      for (const card of q.cards) {
        const { needs, problems } = toRecommendNeeds({ ...GATE, ...card.patch });
        expect(problems, card.id).toEqual([]);
        expect(needs, card.id).toBeDefined();
      }
    }
  });
});

describe("form round trip (so Edit my needs keeps working)", () => {
  it("answers survive going to the form and back", () => {
    const known = { ...GATE, home_charging: "yes", priority: "range", road_conditions: "light_offroad", longest_regular_trip_km: 300 } as const;
    expect(formToPartial(toFormState(known))).toMatchObject(known);
  });

  it("an incomplete saved form is not treated as answers", () => {
    expect(formToPartial({ ...toFormState({ seats_min: 4 }) })).toEqual({});
  });
});

describe("budget from EMI helper", () => {
  it("is deterministic, rounds down to 50,000 and uses the assumed rate", () => {
    expect(EMI_ASSUMPTIONS.annualRatePercent).toBe(9);
    const b = budgetFromEmi(20_000, 5, 200_000);
    expect(b).toBe(budgetFromEmi(20_000, 5, 200_000));
    expect(b! % 50_000).toBe(0);
    // 20,000 a month for 5 years at 9% repays a loan of about 9.6 lakh; plus 2 lakh down
    expect(b).toBe(1_150_000);
  });

  it("more EMI or more down payment never lowers the budget", () => {
    expect(budgetFromEmi(25_000, 5, 200_000)!).toBeGreaterThan(budgetFromEmi(20_000, 5, 200_000)!);
    expect(budgetFromEmi(20_000, 5, 400_000)!).toBeGreaterThan(budgetFromEmi(20_000, 5, 200_000)!);
  });

  it("gives nothing for nonsense or a budget under the minimum", () => {
    expect(budgetFromEmi(0, 5, 0)).toBeNull();
    expect(budgetFromEmi(Number.NaN, 5, 0)).toBeNull();
    expect(budgetFromEmi(-1, 5, 0)).toBeNull();
    expect(budgetFromEmi(2_000, 3, 0)).toBeNull();
    expect(LIMITS.budgetMinInr).toBe(300_000);
  });
});

describe("commute minutes helper", () => {
  it("turns minutes one way into a daily total at the assumed speed, there and back", () => {
    expect(dailyKmFromCommuteMinutes(30)).toBe(20); // 30 min at 20 km/h = 10 km one way
    expect(dailyKmFromCommuteMinutes(60)).toBe(40);
  });

  it("gives nothing for nonsense or out-of-range answers", () => {
    expect(dailyKmFromCommuteMinutes(0)).toBeNull();
    expect(dailyKmFromCommuteMinutes(Number.NaN)).toBeNull();
    expect(dailyKmFromCommuteMinutes(10_000)).toBeNull();
  });
});

describe("editable assumptions", () => {
  it("a higher interest rate lowers the budget and a lower one raises it", () => {
    const at = (rate: number) => budgetFromEmi(20_000, 5, 200_000, rate)!;
    expect(at(12)).toBeLessThan(at(9));
    expect(at(7)).toBeGreaterThan(at(9));
    expect(budgetFromEmi(20_000, 5, 200_000)).toBe(at(9));
  });

  it("gives nothing when the rate is missing, zero, negative or absurd", () => {
    for (const rate of [Number.NaN, 0, -3, 99]) expect(budgetFromEmi(20_000, 5, 200_000, rate)).toBeNull();
    expect(loanFromEmi(20_000, 5, Number.NaN)).toBeNull();
  });

  it("the loan the EMI repays is shown separately from the down payment", () => {
    const loan = loanFromEmi(20_000, 5, 9)!;
    expect(Math.round(loan)).toBeGreaterThan(950_000);
    expect(Math.round(loan)).toBeLessThan(970_000);
  });

  it("the commute estimate follows the speed the buyer enters", () => {
    expect(dailyKmFromCommuteMinutes(30, 20)).toBe(20);
    expect(dailyKmFromCommuteMinutes(30, 40)).toBe(40);
    expect(dailyKmFromCommuteMinutes(30)).toBe(20); // default 20 km/h
    for (const speed of [Number.NaN, 0, 2, 200]) expect(dailyKmFromCommuteMinutes(30, speed)).toBeNull();
  });
});

describe("restoring a saved form", () => {
  it("does not count the form's defaults as answers", () => {
    const saved = toFormState({ ...GATE, home_charging: "yes" });
    expect(formToPartial(saved)).toEqual({ ...GATE, home_charging: "yes" });
  });

  it("keeps non-default choices and chosen features", () => {
    const saved = toFormState({ ...GATE, home_charging: "no", priority: "safety", road_conditions: "rough_roads", must_haves: ["adas"] });
    expect(formToPartial(saved)).toMatchObject({ priority: "safety", road_conditions: "rough_roads", must_haves: ["adas"] });
  });
});
