import { describe, expect, it } from "vitest";
import { carName, formatLakh } from "@/lib/format";

describe("formatLakh (same rule as the engine's fmt_lakh)", () => {
  it.each([
    [699000, "₹6.99 lakh"],
    [200000, "₹2 lakh"],
    [2265000, "₹22.65 lakh"],
    [60000, "₹60,000"],
    [30000, "₹30,000"],
    [1000000, "₹10 lakh"],
  ])("%i → %s", (inr, expected) => {
    expect(formatLakh(inr)).toBe(expected);
  });
});

describe("carName", () => {
  it("joins brand, model and variant", () => {
    expect(carName({ brand: "Tata", model: "Punch.ev", variant: "Smart 30" }, "KEY")).toBe("Tata Punch.ev Smart 30");
  });
  it("falls back to the key when the engine sent no names", () => {
    expect(carName({}, "TATA-KEY")).toBe("TATA-KEY");
  });
});
