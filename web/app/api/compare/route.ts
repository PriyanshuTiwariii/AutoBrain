/**
 * Server route for the comparison: the browser posts the chosen variant keys here; this calls the engine's /compare
 * with the shared secret. The engine's address and secret never reach the browser.
 */
import { isCompareResponse } from "@/lib/compare";
import type { FieldProblem } from "@/lib/types";

export const dynamic = "force-dynamic";

const MAX_BODY_CHARS = 2_000;
const ENGINE_TIMEOUT_MS = 20_000;

function problem(status: number, field: string, message: string): Response {
  const detail: FieldProblem[] = [{ field, message }];
  return Response.json({ detail }, { status });
}

function isProblemList(value: unknown): value is FieldProblem[] {
  return (
    Array.isArray(value) &&
    value.length > 0 &&
    value.every(
      (p) => p && typeof p === "object" && typeof (p as FieldProblem).field === "string" && typeof (p as FieldProblem).message === "string",
    )
  );
}

export async function POST(request: Request): Promise<Response> {
  const secret = process.env.ENGINE_SECRET;
  const engineUrl = (process.env.ENGINE_URL || "http://localhost:8000").replace(/\/+$/, "");

  if (!secret) {
    console.error("ENGINE_SECRET is not set; add it to the .env file at the repo root.");
    return problem(500, "(server)", "The website is not set up correctly yet. Please try again later.");
  }

  const body = await request.text();
  if (body.length > MAX_BODY_CHARS) return problem(413, "(body)", "That request is too large.");

  let upstream: Response;
  try {
    upstream = await fetch(`${engineUrl}/compare`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Engine-Secret": secret },
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(ENGINE_TIMEOUT_MS),
    });
  } catch (error) {
    console.error("Could not reach the engine for /compare:", error instanceof Error ? error.name : "error");
    return problem(503, "(server)", "The advice engine isn't reachable right now. Please try again in a moment.");
  }

  const parsed: unknown = await upstream.json().catch(() => null);
  if (upstream.status === 200 && isCompareResponse(parsed)) return Response.json(parsed);
  if (upstream.status === 422) {
    const detail = (parsed as { detail?: unknown } | null)?.detail;
    if (isProblemList(detail)) return Response.json({ detail }, { status: 422 });
  }
  console.error(`Engine answered ${upstream.status} to /compare`);
  return problem(502, "(server)", "The advice engine gave an unexpected answer. Please try again in a moment.");
}
