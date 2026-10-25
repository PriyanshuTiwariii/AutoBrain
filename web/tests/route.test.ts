import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { POST } from "@/app/api/recommend/route";
import { fixture } from "./helpers";

const SECRET = "s3cret-value-123";
const ENGINE = "http://engine.internal:9999";
const NEEDS = { budget_max_inr: 1_000_000, seats_min: 4, daily_km: 30, home_charging: "yes" };

function post(body: unknown): Request {
  return new Request("http://localhost:3000/api/recommend", {
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

beforeEach(() => {
  vi.stubEnv("ENGINE_SECRET", SECRET);
  vi.stubEnv("ENGINE_URL", ENGINE);
  vi.spyOn(console, "error").mockImplementation(() => {});
});
afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("POST /api/recommend", () => {
  it("calls the engine's /recommend with the secret header and the Needs", async () => {
    const result = fixture("scenario-1");
    const fetchMock = engineReplies(200, result);
    const response = await POST(post(NEEDS));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(`${ENGINE}/recommend`);
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>)["X-Engine-Secret"]).toBe(SECRET);
    expect(JSON.parse(init.body as string)).toEqual(NEEDS);

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(result);
  });

  it("returns the engine's Result byte for byte", async () => {
    const text = JSON.stringify(fixture("scenario-5"));
    engineReplies(200, text);
    expect(await (await POST(post(NEEDS))).text()).toBe(text);
  });

  it("passes the engine's plain-English 422 through", async () => {
    const detail = [{ field: "budget_max_inr", message: "budget_max_inr must be a number of at least 300000" }];
    engineReplies(422, { detail });
    const response = await POST(post({ ...NEEDS, budget_max_inr: 1 }));
    expect(response.status).toBe(422);
    expect(await response.json()).toEqual({ detail });
  });

  it("never shows the browser the secret or the engine's address", async () => {
    for (const [status, body] of [[401, { detail: "Missing or invalid X-Engine-Secret header" }], [500, { detail: "boom" }]] as const) {
      engineReplies(status, body);
      const text = await (await POST(post(NEEDS))).text();
      expect(text).not.toContain(SECRET);
      expect(text).not.toContain("engine.internal");
      expect(text).not.toContain("9999");
      expect(text).not.toContain("X-Engine-Secret");
    }
  });

  it("an engine 401 is the website's setup problem, not the buyer's", async () => {
    engineReplies(401, { detail: "no" });
    const response = await POST(post(NEEDS));
    expect(response.status).toBe(500);
    expect((await response.json()).detail[0].message).toContain("not set up correctly");
  });

  it("an engine failure is a 502 with a plain message", async () => {
    engineReplies(500, { detail: "The engine produced an invalid result." });
    const response = await POST(post(NEEDS));
    expect(response.status).toBe(502);
    expect(JSON.stringify(await response.json())).not.toContain("invalid result");
  });

  it("an unreachable engine is a 503 that does not leak the address", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError(`connect ECONNREFUSED ${ENGINE}`); }));
    const response = await POST(post(NEEDS));
    expect(response.status).toBe(503);
    const text = await response.text();
    expect(text).toContain("isn't reachable");
    expect(text).not.toContain("engine.internal");
  });

  it("refuses to call the engine without a secret", async () => {
    vi.stubEnv("ENGINE_SECRET", "");
    const fetchMock = engineReplies(200, {});
    const response = await POST(post(NEEDS));
    expect(response.status).toBe(500);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects an oversized body without calling the engine", async () => {
    const fetchMock = engineReplies(200, {});
    const response = await POST(post("x".repeat(25_000)));
    expect(response.status).toBe(413);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("defaults to the local engine when ENGINE_URL is not set", async () => {
    vi.stubEnv("ENGINE_URL", "");
    const fetchMock = engineReplies(200, fixture("scenario-1"));
    await POST(post(NEEDS));
    expect((fetchMock.mock.calls[0] as unknown as [string])[0]).toBe("http://localhost:8000/recommend");
  });
});
