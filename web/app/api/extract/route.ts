/**
 * Server route for "Describe what you need": the browser posts the buyer's text here; this calls the
 * engine's /extract with the shared secret. Like /api/recommend, the engine's address and secret never
 * reach the browser. If anything about the LLM step goes wrong the answer is "unavailable" (HTTP 200),
 * so the page shows a short note and the form works exactly as before.
 *
 * The buyer's text is never logged here.
 */
import { UNAVAILABLE, isExtractResponse } from "@/lib/extract";
import type { FieldProblem } from "@/lib/types";

export const dynamic = "force-dynamic";

const MAX_BODY_CHARS = 6_000; // the engine allows 1,500 characters of text; this just stops absurd bodies
// Worst case on the engine: the first model times out (15 s) and the fallback model is used (up to 15 s more)
const ENGINE_TIMEOUT_MS = 45_000;

function unavailable(): Response {
  return Response.json(UNAVAILABLE);
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
    return unavailable();
  }

  const body = await request.text();
  if (body.length > MAX_BODY_CHARS) {
    return Response.json({ detail: [{ field: "text", message: "That message is too long." }] }, { status: 422 });
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${engineUrl}/extract`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Engine-Secret": secret },
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(ENGINE_TIMEOUT_MS),
    });
  } catch (error) {
    // Only the error's name: its message could quote what was sent
    console.error("Could not reach the engine for /extract:", error instanceof Error ? error.name : "error");
    return unavailable();
  }

  if (upstream.status === 200) {
    const parsed: unknown = await upstream.json().catch(() => null);
    return isExtractResponse(parsed) ? Response.json(parsed) : unavailable();
  }

  if (upstream.status === 422) {
    const parsed: unknown = await upstream.json().catch(() => null);
    const detail = (parsed as { detail?: unknown } | null)?.detail;
    if (isProblemList(detail)) return Response.json({ detail }, { status: 422 });
    return unavailable();
  }

  console.error(`Engine answered ${upstream.status} to /extract`);
  return unavailable();
}
