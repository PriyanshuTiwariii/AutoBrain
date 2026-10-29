# Backlog

Things we have decided to do later. Not in the current demo. The order is not a priority order.

## Before any public deployment

- **Production readiness.** A blunt review (measurements, blockers, plan, capacity maths for 1M users) is in
  `docs/PRODUCTION_READINESS.md`. The first items: rate limits and an LLM spend cap on every route, a capped
  pool for LLM calls, caching of `/cars`, `/compare` and next-question answers, Docker and CI, monitoring.
- **Upgrade Next.js and PostCSS.** The website is on Next.js 14 (as the project asked). `npm audit --omit=dev`
  (2026-10-25) reports a critical finding on `next` (mostly denial-of-service: Server Components, the image
  optimisation API, middleware) and a high finding on `postcss` (bundled by Next). Both are fixed only in a newer
  major version of Next (npm suggests 16.x). This is fine for local demos. It must be done, and `npm audit`
  re-run clean, before the site is reachable by the public. Re-check the pages, the PDF print layout and the
  tests after the upgrade.

## Website

- **Add test-drive and quote buttons** to the results page, as in the mockups ("Book a test drive for my top
  pick", "Get on-road quotes from 3 dealers"). They need lead capture with an unticked consent box (see the
  leads section of `docs/DESIGN.md`) and a legal review of the consent wording before any name or phone number
  is collected. Nothing is shared with a dealer without consent.
