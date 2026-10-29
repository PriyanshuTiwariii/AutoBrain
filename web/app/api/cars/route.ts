/**
 * Server route for the comparison pickers: asks the engine's GET /cars (every variant in the data release) with the
 * shared secret. The engine's address and secret never reach the browser.
 */
import { isCarsResponse } from "@/lib/compare";
import type { FieldProblem } from "@/lib/types";

export const dynamic = "force-dynamic";

const ENGINE_TIMEOUT_MS = 20_000;

function problem(status: number, field: string, message: string): Response {
  const detail: FieldProblem[] = [{ field, message }];
  return Response.json({ detail }, { status });
}

export async function GET(): Promise<Response> {
  const secret = process.env.ENGINE_SECRET;
  const engineUrl = (process.env.ENGINE_URL || "http://localhost:8000").replace(/\/+$/, "");

  if (!secret) {
    console.error("ENGINE_SECRET is not set; add it to the .env file at the repo root.");
    return problem(500, "(server)", "The website is not set up correctly yet. Please try again later.");
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${engineUrl}/cars`, {
      headers: { "X-Engine-Secret": secret },
      cache: "no-store",
      signal: AbortSignal.timeout(ENGINE_TIMEOUT_MS),
    });
  } catch (error) {
    console.error("Could not reach the engine for /cars:", error instanceof Error ? error.name : "error");
    return problem(503, "(server)", "The advice engine isn't reachable right now. Please try again in a moment.");
  }

  const parsed: unknown = await upstream.json().catch(() => null);
  if (upstream.status === 200 && isCarsResponse(parsed)) return Response.json(parsed);
  console.error(`Engine answered ${upstream.status} to /cars`);
  return problem(502, "(server)", "The advice engine gave an unexpected answer. Please try again in a moment.");
}
