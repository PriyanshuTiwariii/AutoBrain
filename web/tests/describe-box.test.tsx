import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import DescribeBox, { EXAMPLE_TEXT } from "@/components/DescribeBox";
import { MAX_TEXT_CHARS, UNAVAILABLE } from "@/lib/extract";
import { EMPTY_FORM } from "@/lib/needs";

function render(): string {
  return renderToStaticMarkup(<DescribeBox onApply={() => ({ form: EMPTY_FORM, filled: [], ignored: [] })} />);
}

describe("the Describe box", () => {
  const html = render();

  it("is a labelled section with a text box and a button that only fills in the form", () => {
    expect(html).toContain("Describe what you need");
    expect(html).toContain("Fill in the form for me");
    expect(html).toContain("<textarea");
    expect(html).toContain(`maxLength="${MAX_TEXT_CHARS}"`);
    expect(html).toContain(EXAMPLE_TEXT);
  });

  it("promises the buyer they still check everything, and that the message is not saved", () => {
    expect(html).toContain("you check it and change anything before you");
    expect(html).toContain("Your message is not saved.");
  });

  it("starts with the button off until something is typed, and no note showing", () => {
    expect(html).toMatch(/<button[^>]*disabled[^>]*>Fill in the form for me/);
    expect(html).not.toContain("We filled in");
    expect(html).not.toContain(UNAVAILABLE.message as string);
  });

  it("is a button of type 'button', so it can never submit the form by itself", () => {
    expect(html).toMatch(/<button[^>]*type="button"/);
    expect(html).not.toContain('type="submit"');
  });
});
