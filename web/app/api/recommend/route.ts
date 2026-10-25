/**
 * Server route: the browser posts the Needs here; this calls the engine's /recommend with the shared
 * secret. The engine's address and secret exist only on the server and never reach the browser.
 */
import type { FieldProblem } from "@/lib/types";

export const dynamic = "force-dynamic";

const MAX_BODY_CHARS = 20_000;
const ENGINE_TIMEOUT_MS = 20_000;

function problem(status: number, field: string, message: string): Response {
  const detail: FieldProblem[] = [{ field, message }];
  return Response.json({ detail }, { status });
}

function isProblemList(value: unknown): value is FieldProblem[] {
  return (
    Array.isArray(value) &&
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
    upstream = await fetch(`${engineUrl}/recommend`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Engine-Secret": secret },
      body,
      cache: "no-store",
      signal: AbortSignal.timeout(ENGINE_TIMEOUT_MS),
    });
  } catch (error) {
    console.error("Could not reach the engine:", error instanceof Error ? error.message : error);
    return problem(503, "(server)", "The advice engine isn't reachable right now. Please try again in a moment.");
  }

  if (upstream.status === 200) {
    // Pass the Result through untouched: every number the buyer sees is exactly what the engine returned
    return new Response(await upstream.text(), { status: 200, headers: { "Content-Type": "application/json" } });
  }

  if (upstream.status === 422) {
    const parsed: unknown = await upstream.json().catch(() => null);
    const detail = (parsed as { detail?: unknown } | null)?.detail;
    if (isProblemList(detail)) return Response.json({ detail }, { status: 422 });
    return problem(422, "form", "Some of your answers could not be used. Please check the form.");
  }

  console.error(`Engine answered ${upstream.status} to /recommend`);
  if (upstream.status === 401) {
    return problem(500, "(server)", "The website is not set up correctly yet. Please try again later.");
  }
  return problem(502, "(server)", "The advice engine had a problem and could not give a result. Please try again.");
}
