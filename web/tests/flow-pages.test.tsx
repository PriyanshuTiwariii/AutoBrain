import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import EvStartPage from "@/app/start/ev/page";
import StartPage from "@/app/start/page";
import Landing from "@/app/page";

describe("the first screens", () => {
  it("landing page invites the buyer to start, with no brand names in the headline", () => {
    const html = renderToStaticMarkup(<Landing />);
    expect(html).toContain('href="/start"');
    expect(html).toContain("Honest EV advice for first-time buyers");
    const headline = html.match(/<h1[^>]*>(.*?)<\/h1>/)?.[1] ?? "";
    expect(headline).not.toMatch(/Tata|Mahindra/);
  });

  it("first question: electric car goes on, petrol or diesel says it is not covered yet", () => {
    const html = renderToStaticMarkup(<StartPage />);
    expect(html).toContain("What kind of car are you looking at?");
    expect(html).toContain('href="/start/ev"');
    expect(html).toContain("Petrol or diesel");
    expect(html).toContain("Coming later");
    expect(html).not.toContain("We only give advice on electric cars for now"); // shown only after tapping it
  });

  it("second question for EVs: find a car, or compare shortlisted cars", () => {
    const html = renderToStaticMarkup(<EvStartPage />);
    expect(html).toContain("Find the right EV for me");
    expect(html).toContain('href="/find"');
    expect(html).toContain("Compare EVs I have shortlisted");
    expect(html).toContain('href="/compare"');
    expect(html).toContain('href="/start"'); // back
  });
});
