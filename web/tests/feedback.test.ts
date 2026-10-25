import { describe, expect, it } from "vitest";
import { buildFeedbackUrl, type FeedbackContext } from "@/lib/feedback";
import { newVisitId } from "@/lib/storage";

const ctx: FeedbackContext = {
  visitId: "visit-abc",
  resultId: "d4d0b1a056fc54e5",
  datasetVersion: "2026-10-25-r2",
  topPick: "TATA-PUNCHEV-SMART30-30",
};

describe("buildFeedbackUrl", () => {
  it("is null when no form is set up or the URL is not a URL", () => {
    expect(buildFeedbackUrl(undefined, ctx)).toBeNull();
    expect(buildFeedbackUrl("", ctx)).toBeNull();
    expect(buildFeedbackUrl("   ", ctx)).toBeNull();
    expect(buildFeedbackUrl("not a url", ctx)).toBeNull();
  });

  it("attaches the visit ID, result ID, dataset version and top pick", () => {
    const url = new URL(buildFeedbackUrl("https://forms.gle/example?x=1", ctx) as string);
    expect(url.searchParams.get("x")).toBe("1");
    expect(url.searchParams.get("visit_id")).toBe("visit-abc");
    expect(url.searchParams.get("result_id")).toBe("d4d0b1a056fc54e5");
    expect(url.searchParams.get("dataset_version")).toBe("2026-10-25-r2");
    expect(url.searchParams.get("top_pick")).toBe("TATA-PUNCHEV-SMART30-30");
  });

  it("leaves out the top pick when there was none", () => {
    const url = new URL(buildFeedbackUrl("https://forms.gle/example", { ...ctx, topPick: null }) as string);
    expect(url.searchParams.has("top_pick")).toBe(false);
  });

  it("uses Google Form entry IDs when they are configured", () => {
    const url = new URL(
      buildFeedbackUrl("https://docs.google.com/forms/d/e/ID/viewform", ctx, { visit: "111", result: "222", dataset: "333", topPick: "444" }) as string,
    );
    expect(url.searchParams.get("usp")).toBe("pp_url");
    expect(url.searchParams.get("entry.111")).toBe("visit-abc");
    expect(url.searchParams.get("entry.222")).toBe("d4d0b1a056fc54e5");
    expect(url.searchParams.get("entry.333")).toBe("2026-10-25-r2");
    expect(url.searchParams.get("entry.444")).toBe("TATA-PUNCHEV-SMART30-30");
    expect(url.searchParams.has("visit_id")).toBe(false);
  });
});

describe("the visit ID", () => {
  it("is random per visit and is not derived from the result", () => {
    const ids = new Set(Array.from({ length: 50 }, () => newVisitId()));
    expect(ids.size).toBe(50);
    for (const id of ids) {
      expect(id.length).toBeGreaterThanOrEqual(32);
      expect(id).not.toContain(ctx.resultId);
    }
  });
});
