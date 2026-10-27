import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { POST } from "@/app/api/next-question/route";
import { questionFixture } from "./helpers";

const SECRET = "s3cret-value-123";
const ENGINE = "http://engine.internal:9999";

function post(body: unknown): Request {
  return new Request("http://localhost:3000/api/next-question", {
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

describe("POST /api/next-question", () => {
  it("passes the body to the engine with the secret and returns its question", async () => {
    const fetchMock = engineReplies(200, questionFixture("budget"));
    const response = await POST(post({ needs: {}, asked: [] }));
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(questionFixture("budget"));
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(`${ENGINE}/next_question`);
    expect((init.headers as Record<string, string>)["X-Engine-Secret"]).toBe(SECRET);
    expect(init.body).toBe(JSON.stringify({ needs: {}, asked: [] }));
  });

  it("never sends the engine's secret or address to the browser", async () => {
    engineReplies(200, questionFixture("optional"));
    const text = await (await POST(post({ needs: {} }))).text();
    expect(text).not.toContain(SECRET);
    expect(text).not.toContain("engine.internal");
  });

  it("passes the engine's plain-English 422 problems through", async () => {
    engineReplies(422, { detail: [{ field: "needs.budget_max_inr", message: "needs.budget_max_inr is not valid" }] });
    const response = await POST(post({ needs: { budget_max_inr: 1 } }));
    expect(response.status).toBe(422);
    expect((await response.json()).detail[0].field).toBe("needs.budget_max_inr");
  });

  it("answers 502 when the engine's answer is not a question", async () => {
    engineReplies(200, { nonsense: true });
    expect((await POST(post({ needs: {} }))).status).toBe(502);
  });

  it("answers 503 when the engine cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("connect ECONNREFUSED"); }));
    expect((await POST(post({ needs: {} }))).status).toBe(503);
  });

  it("answers 500 when the website has no secret, and 413 for an absurd body", async () => {
    vi.stubEnv("ENGINE_SECRET", "");
    expect((await POST(post({ needs: {} }))).status).toBe(500);
    vi.stubEnv("ENGINE_SECRET", SECRET);
    expect((await POST(post("x".repeat(30_000)))).status).toBe(413);
  });
});
