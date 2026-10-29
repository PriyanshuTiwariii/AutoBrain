import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GET as getCars } from "@/app/api/cars/route";
import { POST as postCompare } from "@/app/api/compare/route";
import { compareFixture } from "./helpers";

const SECRET = "s3cret-value-123";
const ENGINE = "http://engine.internal:9999";
const CARS = { dataset_version: "r", cars: [{ variant_key: "A", brand: "Tata", model: "M", variant: "V", pricing_type: "battery included" }] };

function post(body: unknown): Request {
  return new Request("http://localhost:3000/api/compare", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: typeof body === "string" ? body : JSON.stringify(body),
  });
}

function engineReplies(status: number, body: unknown) {
  const fetchMock = vi.fn(async () => new Response(JSON.stringify(body), { status }));
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

describe("GET /api/cars", () => {
  it("asks the engine with the secret and returns its list", async () => {
    const fetchMock = engineReplies(200, CARS);
    const response = await getCars();
    expect(await response.json()).toEqual(CARS);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(`${ENGINE}/cars`);
    expect((init.headers as Record<string, string>)["X-Engine-Secret"]).toBe(SECRET);
  });

  it("never leaks the secret or the engine's address", async () => {
    engineReplies(200, CARS);
    const text = await (await getCars()).text();
    expect(text).not.toContain(SECRET);
    expect(text).not.toContain("engine.internal");
  });

  it("answers 502 for a malformed list, 503 when the engine is down, 500 with no secret", async () => {
    engineReplies(200, { nope: true });
    expect((await getCars()).status).toBe(502);
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("ECONNREFUSED"); }));
    expect((await getCars()).status).toBe(503);
    vi.stubEnv("ENGINE_SECRET", "");
    expect((await getCars()).status).toBe(500);
  });
});

describe("POST /api/compare", () => {
  it("passes the keys to the engine and returns its comparison", async () => {
    const fetchMock = engineReplies(200, compareFixture("three"));
    const body = { variant_keys: ["A", "B", "C"] };
    const response = await postCompare(post(body));
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(compareFixture("three"));
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(`${ENGINE}/compare`);
    expect(init.body).toBe(JSON.stringify(body));
    expect((init.headers as Record<string, string>)["X-Engine-Secret"]).toBe(SECRET);
  });

  it("passes the engine's plain-English problems through", async () => {
    engineReplies(422, { detail: [{ field: "variant_keys[1]", message: "variant_keys[1] is not a car in our data" }] });
    const response = await postCompare(post({ variant_keys: ["A", "Z"] }));
    expect(response.status).toBe(422);
    expect((await response.json()).detail[0].field).toBe("variant_keys[1]");
  });

  it("answers 502 for a malformed comparison, 503 when the engine is down, 413 for a huge body, 500 with no secret", async () => {
    engineReplies(200, { cars: [] });
    expect((await postCompare(post({ variant_keys: ["A", "B"] }))).status).toBe(502);
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("ECONNREFUSED"); }));
    expect((await postCompare(post({ variant_keys: ["A", "B"] }))).status).toBe(503);
    expect((await postCompare(post("x".repeat(3_000)))).status).toBe(413);
    vi.stubEnv("ENGINE_SECRET", "");
    expect((await postCompare(post({ variant_keys: ["A", "B"] }))).status).toBe(500);
  });
});
