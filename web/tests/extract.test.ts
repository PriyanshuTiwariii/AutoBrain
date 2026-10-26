import { describe, expect, it } from "vitest";
import {
  EXTRACT_STATUSES, MAX_TEXT_CHARS, REQUIRED_FIELDS, UNAVAILABLE, applyExtraction, isExtractResponse, lakhText, noteFor,
} from "@/lib/extract";
import { EMPTY_FORM, buildNeeds, type FormState } from "@/lib/needs";
import type { ExtractResponse } from "@/lib/types";
import { contract, extractFixture } from "./helpers";

const typed: FormState = {
  ...EMPTY_FORM, budgetLakh: "9", seats: "2", dailyKm: "10", tripKm: "100", homeCharging: "unsure",
  mustHaves: ["esp"], niceToHaves: ["awd"], priority: "range",
};

function response(needs: ExtractResponse["needs"], over: Partial<ExtractResponse> = {}): ExtractResponse {
  return { ...UNAVAILABLE, status: "read", message: null, needs, ...over };
}

describe("applyExtraction, on real engine responses", () => {
  it("fills in every field the engine read, with the budget shown in lakh", () => {
    const { form, filled } = applyExtraction(EMPTY_FORM, extractFixture("complete"));
    expect(form).toMatchObject({
      budgetLakh: "12.5", seats: "5", dailyKm: "50", homeCharging: "no", priority: "safety",
      mustHaves: ["adas", "camera_360"], niceToHaves: ["sunroof"],
    });
    expect(filled).toEqual(["budget", "seats", "daily driving", "home charging", "must-haves", "nice-to-haves", "priority"]);
  });

  it("fills in road conditions when the engine read them", () => {
    const { form, filled } = applyExtraction(EMPTY_FORM, response({ road_conditions: "light_offroad" }));
    expect(form.roadConditions).toBe("light_offroad");
    expect(filled).toEqual(["road conditions"]);
    expect(applyExtraction(EMPTY_FORM, response({})).form.roadConditions).toBe("city_highway");
  });

  it("the filled form builds a valid Needs, so the buyer can just press the button", () => {
    const { form } = applyExtraction({ ...EMPTY_FORM }, extractFixture("complete"));
    const { needs, problems } = buildNeeds(form);
    expect(problems).toEqual([]);
    expect(needs).toMatchObject({ budget_max_inr: 1_250_000, seats_min: 5, daily_km: 50, home_charging: "no" });
  });

  it("only touches what the engine returned: whatever the buyer typed stays", () => {
    const { form, filled } = applyExtraction(typed, extractFixture("missing-budget"));
    expect(filled).toEqual(["seats", "home charging"]);
    expect(form).toEqual({ ...typed, seats: "4", homeCharging: "yes" });
  });

  it("a partial answer fills the fields that were read and leaves the rest", () => {
    const { form, filled } = applyExtraction(EMPTY_FORM, extractFixture("partial"));
    expect(filled).toEqual(["seats", "daily driving"]);
    expect(form.budgetLakh).toBe("");
  });

  it("off-topic and unavailable answers change nothing", () => {
    for (const name of ["off-topic", "unavailable"] as const) {
      const { form, filled, ignored } = applyExtraction(typed, extractFixture(name));
      expect(form).toEqual(typed);
      expect(filled).toEqual([]);
      expect(ignored).toEqual([]);
    }
  });

  it("reports what the form cannot take instead of dropping it silently", () => {
    const { ignored, form } = applyExtraction(EMPTY_FORM, extractFixture("complete"));
    expect(ignored).toEqual(["body type", "excluded cars"]);
    expect(form).not.toHaveProperty("bodyTypes");
  });

  it("a must-have read from the text replaces the same feature among the nice-to-haves", () => {
    const { form } = applyExtraction(
      { ...EMPTY_FORM, niceToHaves: ["adas", "sunroof"] },
      response({ must_haves: ["adas"] }),
    );
    expect(form.mustHaves).toEqual(["adas"]);
    expect(form.niceToHaves).toEqual(["sunroof"]);
  });

  it("does not change the form it was given", () => {
    const before = structuredClone(typed);
    applyExtraction(typed, extractFixture("complete"));
    expect(typed).toEqual(before);
  });

  it("ignores values the form could not hold, even if one ever slipped through", () => {
    const { form, filled } = applyExtraction(
      EMPTY_FORM,
      response({ seats_min: 9, daily_km: 900, budget_max_inr: 5, priority: "pirate" as never, home_charging: "always" as never, must_haves: ["wifi" as never] }),
    );
    expect(form).toEqual(EMPTY_FORM);
    expect(filled).toEqual([]);
  });
});

describe("lakhText", () => {
  it.each([[1_500_000, "15"], [1_250_000, "12.5"], [800_000, "8"], [1_234_567, "12.3457"], [15_000_000, "150"]])("%i → %s", (inr, text) => {
    expect(lakhText(inr)).toBe(text);
  });
});

describe("noteFor", () => {
  it("tells the buyer what was filled in and to check it", () => {
    const resp = extractFixture("complete");
    const note = noteFor(resp, applyExtraction(EMPTY_FORM, resp));
    expect(note.tone).toBe("ok");
    expect(note.lines[0]).toContain("We filled in: budget, seats");
    expect(note.lines[0]).toContain("Check every field below");
    expect(note.lines.join(" ")).toContain("body type, excluded cars");
    expect(note.lines.join(" ")).not.toContain("One more thing");
  });

  it("shows the engine's one question as it came", () => {
    const resp = extractFixture("missing-budget");
    const note = noteFor(resp, applyExtraction(EMPTY_FORM, resp));
    expect(note.lines.at(-1)).toBe(`One more thing: ${resp.question}`);
    expect(note.lines.filter((l) => l.startsWith("One more thing"))).toHaveLength(1);
  });

  it("a partial answer warns and names what could not be used", () => {
    const resp = extractFixture("partial");
    const note = noteFor(resp, applyExtraction(EMPTY_FORM, resp));
    expect(note.tone).toBe("warn");
    expect(note.lines.join(" ")).toContain("We couldn't use what we read for: budget");
  });

  it("off-topic and unavailable show the engine's short note and nothing else", () => {
    for (const name of ["off-topic", "unavailable"] as const) {
      const resp = extractFixture(name);
      const note = noteFor(resp, applyExtraction(EMPTY_FORM, resp));
      expect(note).toEqual({ tone: "info", lines: [resp.message] });
    }
    expect(UNAVAILABLE.message).toBe(extractFixture("unavailable").message);
  });
});

describe("isExtractResponse", () => {
  it("accepts every real engine response", () => {
    for (const name of ["complete", "missing-budget", "partial", "off-topic", "unavailable"] as const) {
      expect(isExtractResponse(extractFixture(name))).toBe(true);
    }
  });

  it.each([null, undefined, "x", 5, [], {}, { status: "read" }, { ...UNAVAILABLE, status: "weird" }, { ...UNAVAILABLE, needs: [] }, { ...UNAVAILABLE, complete: "yes" }])(
    "rejects %j",
    (value) => {
      expect(isExtractResponse(value)).toBe(false);
    },
  );
});

describe("the website stays in step with the extract contracts", () => {
  it("statuses, required fields and the text limit", () => {
    const response = contract("extract.response");
    expect([...EXTRACT_STATUSES].sort()).toEqual([...response.properties.status.enum].sort());
    expect(REQUIRED_FIELDS).toEqual(response.properties.missing.items.enum);
    expect(MAX_TEXT_CHARS).toBe(contract("extract.request").properties.text.maxLength);
  });
});
