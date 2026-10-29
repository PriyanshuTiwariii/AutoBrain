# Production readiness review (2026-10-29)

Status: **not production-grade yet. Parked for later.** This records an honest review of the app after the guided intake,
the EV or non-EV start flow and the car comparison were added. Nothing here has been fixed yet.

## Verdict

The application is correct and well-tested (365 engine tests, 206 web tests), and the engine design (pure, deterministic,
stateless, read-only data in memory) is the right shape to scale to 1M users by adding copies. The gaps are around the
engine: abuse protection, the LLM path, caching, deployment and monitoring. The most serious is that **anyone can drain the
OpenAI budget**, because nothing limits calls to the text-box route.

## What was measured

Measured on a Windows dev machine, one engine process, Python 3.13, over `localhost`. This is pessimistic compared with Linux.
The 2-4 second tail latencies at 20-100 concurrent clients are partly a single-process and Windows artifact; read the p50 figures.
The load test used a throwaway engine on another port, with Python's `http.client` and keep-alive connections.

| Operation | Compute time | Via HTTP, 1 client | Throughput, 1 process |
| --- | --- | --- | --- |
| Recommend | 1.1 ms | 5.4 ms | about 100 req/s |
| Next question (with sensitivity check) | 8.6 ms | 11.5 ms | about 45-65 req/s |
| Compare 3 cars | 0.2 ms | 4.9 ms | about 100-140 req/s |
| List cars | 0.1 ms | 6.1 ms | about 80-100 req/s |
| Data release load at startup | 31 ms | | |

- Zero errors at 1, 20 and 100 concurrent clients (about 4 seconds each).
- Payloads: cars list about 20 KB, comparison about 10 KB, recommendation about 8 KB.
- Every response is checked against its JSON schema before it is sent. That costs about 1.6 ms (`/recommend`), 2.7 ms (`/compare`)
  and 3.8 ms (`/cars`), which is most of the per-request time and the reason a trivial endpoint tops out near 100 req/s.
- One sensitivity field costs about 3.8 ms. The question picker tries about 13 answers (3 fields) per call.
- `curl` to `localhost` takes about 200 ms on this machine (IPv6 tried first). That is a Windows artifact, not an app problem.

To repeat the measurements, start the engine on a spare port without `--reload` (`python -m uvicorn app.main:app --port 8001`),
time `build_result`, `next_question`, `compare_cars` and `list_cars` directly, then drive the HTTP routes with many threads.

## What the recent changes cost

1. **Schema validation on every response.** Wasted CPU in production. `/cars` and `/compare` return the same answer for the same input
   until the data release changes, so they should be cached. Validation belongs in tests or on a small sample of requests.
   The habit started with `/recommend` and was copied into the four new routes.
2. **The next-question check is the heaviest new thing.** It re-ranks all 87 cars about 13 times per call (8.6 ms). The cost grows with
   cars x fields x answers; at about 1,000 cars it would be about 100 ms per tap. The answers are deterministic, so caching by the
   answers so far would make almost every call free.
3. **`/cars` is fetched fresh on every Compare page load** (marked never-cache). It is the same 20 KB for everyone; a CDN should serve it.
4. **Extra round trips.** Each card tap goes browser, Next.js route, engine. A 7-question flow makes 7 round trips plus the extraction.
5. **Handlers run CPU work inline.** `/recommend` and `/compare` do their work inside `async def` handlers, so each request blocks the
   event loop for its compute time. Harmless at about 5 ms, but it caps one worker at roughly 100-200 req/s.

## Blockers, in priority order

1. **No rate limiting or bot protection anywhere.** The text-box route calls a paid LLM; a script in a loop can run up the bill, and
   nothing stops it. The other routes can be hammered too.
2. **The LLM path can starve the whole engine.** Each extraction holds a worker thread for up to 15 s (30 s with the fallback model).
   The engine's thread pool (about 40 slots) is shared with the question endpoint, so about 40 people typing at once could make
   everyone's next question wait. LLM calls need their own capped pool, with a queue or a "busy, use the questions" fallback.
3. **Next.js 14 has known critical findings** (see `BACKLOG.md`). Must be upgraded before the site is public.
4. **Nothing to deploy with.** No Dockerfile, no CI, no staging, no production start command (it runs with `--reload` and
   `npm run dev`). ESLint is ignored during builds.
5. **No monitoring.** No metrics, error tracking, request IDs or alerts. Logs are privacy-safe (buyer text is never logged), but they are
   not monitoring.
6. **One shared secret protects the engine** (`X-Engine-Secret`). Fine only if the engine is on a private network and never reachable
   from the internet. The network must enforce that, not just the secret. Check `DEV_CORS` is off.
7. **No end-to-end browser tests and no load test in CI.** All tests are unit or integration tests.
8. **Security headers.** No content security policy or other response headers beyond `poweredByHeader: false`.

## Can it reach 1M users?

Everything is stateless (no database, no server sessions, read-only data in memory), so capacity is added by running more copies.

- **1M users per month:** about 10 engine calls per session is about 4 requests per second on average and about 40 at peak (10x).
  That is 1-2 engine workers.
- **Heavy load:** 100,000 users active at the same moment is roughly 10,000 requests per second, on the order of 50-100 workers behind
  a load balancer. Expensive but straightforward, and caching cuts it a lot. One million simultaneous users is not a realistic target.
- **What actually limits scale:** the OpenAI rate limits and cost, not the engine. Each text-box call sends about 1,000 tokens of fixed
  instructions plus about 500 tokens of response schema, whatever the user types. A rupee estimate needs the chosen model and its price.
- The pages `/start`, `/start/ev` and `/find` are static, so a CDN absorbs most of the page traffic. The API routes are the dynamic part.

## What is already good

- Pure, deterministic engine with no hidden state: scales horizontally and caches safely.
- The LLM can be switched off and the whole flow still works.
- Buyer text is never logged; the engine secret and address never reach the browser.
- Unknown data stays unknown; the comparison withholds winners when figures are not like for like.
- Strong test coverage, and contract-first changes.

## Plan, in order

1. **Before any public URL**
   - Per-IP rate limits on every route, much stricter on the text-box route.
   - A daily LLM spend cap with a graceful "use the questions instead" fallback.
   - Upgrade Next.js (and PostCSS) and re-run `npm audit`.
2. **Engine hardening**
   - Several workers (for example gunicorn with uvicorn workers, one per CPU).
   - A separate capped pool for LLM calls, so they cannot starve other endpoints.
   - Cache `/cars`, `/compare` and next-question answers in memory (the engine is deterministic, so this is safe). Drop schema
     validation from the hot path (keep it in tests and sample it in production).
   - Cache `/cars` at the CDN.
3. **Delivery**
   - A Dockerfile per service, CI that runs lint, unit tests and a load test, and a staging environment.
   - Run the engine on a private network only.
4. **Operations**
   - Error tracking, request IDs, basic metrics, and alerts on latency, error rate and LLM spend.
5. **Then**
   - End-to-end browser tests (including the LLM-off flow and a 390 px phone), and tests with real first-time buyers.
   - Log 20-30 realistic buyers against the question picker's "worth asking" threshold (1.5) to validate it.

Steps 1 and 2 are mostly code in this repo. Steps 3 and 4 depend on where it will be hosted, which is not decided yet.

## Capacity targets to check after the fixes

- p95 under 100 ms for every engine route at 50 concurrent clients on one worker.
- At least 1,000 req/s on a 4-worker engine for the cached routes.
- No engine route slows down while 100 text-box requests are waiting on the LLM.
- Daily LLM spend never exceeds the cap, and the fallback to the plain questions works when it is hit.
