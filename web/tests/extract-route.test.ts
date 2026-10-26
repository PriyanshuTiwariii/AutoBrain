import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { POST } from "@/app/api/extract/route";
import { UNAVAILABLE } from "@/lib/extract";
import { extractFixture } from "./helpers";

const SECRET = "s3cret-value-123";
const ENGINE = "http://engine.internal:9999";
const TEXT = "ZEBRA-PHRASE-7731 budget 15 lakh family of 4";

function post(body: unknown): Request {
  return new Request("http://localhost:3000/api/extract", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
}

function engineReplies(status: number, body: unknown) {
  const fetchMock = vi.fn(async () => new Response(typeof body === "string" ? body : JSON.stringify(body), { status }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

let consoleCalls: string[] = [];

beforeEach(() => {
  vi.stubEnv("ENGINE_SECRET", SECRET);
  vi.stubEnv("ENGINE_URL", ENGINE);
  consoleCalls = [];
  for (const method of ["error", "warn", "log", "info"] as const) {
    vi.spyOn(console, method).mockImplementation((...args: unknown[]) => {
      consoleCalls.push(args.map(String).join(" "));
    });
  }
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("POST /api/extract", () => {
  it("calls the engine's /extract with the secret and the buyer's text, and returns the answer untouched", async () => {
    const answer = extractFixture("complete");
    const fetchMock = engineReplies(200, answer);
    const response = await POST(post({ text: TEXT }));

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(`${ENGINE}/extract`);
    expect((init.headers as Record<string, string>)["X-Engine-Secret"]).toBe(SECRET);
    expect(JSON.parse(init.body as string)).toEqual({ text: TEXT });
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(answer);
  });

  it("passes the engine's plain-English 422 through", async () => {
    const detail = [{ field: "text", message: "text must be at most 1500 characters" }];
    engineReplies(422, { detail });
    const response = await POST(post({ text: "x" }));
    expect(response.status).toBe(422);
    expect(await response.json()).toEqual({ detail });
  });

  it.each([
    [401, { detail: "Missing or invalid X-Engine-Secret header" }],
    [500, { detail: "boom" }],
    [502, "not json"],
    [200, { status: "nonsense" }],
    [200, "not json"],
    [422, { detail: "not a list" }],
  ])("anything wrong on the engine side (%i) is an 'unavailable' note with a 200, never an error page", async (status, body) => {
    engineReplies(status, body);
    const response = await POST(post({ text: TEXT }));
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(UNAVAILABLE);
  });

  it("an unreachable engine is 'unavailable' too, without leaking the address", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError(`connect ECONNREFUSED ${ENGINE} ${TEXT}`); }));
    const response = await POST(post({ text: TEXT }));
    expect(response.status).toBe(200);
    const text = await response.text();
    expect(JSON.parse(text)).toEqual(UNAVAILABLE);
    expect(text).not.toContain("engine.internal");
  });

  it("a timeout is 'unavailable'", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new DOMException("The operation timed out", "TimeoutError"); }));
    expect(await (await POST(post({ text: TEXT }))).json()).toEqual(UNAVAILABLE);
  });

  it("without a secret it does not call the engine", async () => {
    vi.stubEnv("ENGINE_SECRET", "");
    const fetchMock = engineReplies(200, extractFixture("complete"));
    expect(await (await POST(post({ text: TEXT }))).json()).toEqual(UNAVAILABLE);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects an absurdly large body without calling the engine", async () => {
    const fetchMock = engineReplies(200, extractFixture("complete"));
    const response = await POST(post("x".repeat(7_000)));
    expect(response.status).toBe(422);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("never shows the browser the secret or the engine's address", async () => {
    for (const [status, body] of [[401, { detail: "no" }], [500, {}], [200, extractFixture("complete")]] as const) {
      engineReplies(status, body);
      const text = await (await POST(post({ text: TEXT }))).text();
      for (const secret of [SECRET, "engine.internal", "9999", "X-Engine-Secret"]) expect(text).not.toContain(secret);
    }
  });

  it("never logs the buyer's text", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new Error(`failed for ${TEXT}`); }));
    await POST(post({ text: TEXT }));
    engineReplies(500, { detail: TEXT });
    await POST(post({ text: TEXT }));
    expect(consoleCalls.length).toBeGreaterThan(0);
    expect(consoleCalls.join("\n")).not.toContain("ZEBRA");
    expect(consoleCalls.join("\n")).not.toContain("15 lakh");
  });
});
