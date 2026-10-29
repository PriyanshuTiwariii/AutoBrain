# Guided intake (`/find`)

A buyer with no car knowledge describes their life; the system asks easy follow-ups until it can recommend.

```
Buyer text (optional) -> /extract (LLM call 1) -> known Needs -> /next_question (pure engine) -> one easy question
        ^                                                                                           |
        +------------------------- card tap, helper, or typed answer <------------------------------+
                                                       |
                                       "Show my shortlist" -> /recommend (unchanged)
```

## Rules
- The LLM only reads typed text (call 1). It never chooses a question, a car or a number.
- `/next_question` is pure and deterministic. Question text, cards and helpers are fixed templates in `engine/app/questions.py`.
- Required, in this order: budget, seats, daily km, home charging. Skipped when known. Home charging may be "not sure".
- Optional (roads, what matters most, long trips): asked only if the possible answers change the top 3 cars or the best match
  (`MATERIAL_SCORE`), at most 3, never repeated. "Show my shortlist now" is available once budget, seats and daily km are known.
- Cards set only the field they answer. No card sets `must_haves` or `nice_to_haves`. "Not sure" never becomes yes or no.
- The "What we understood" chips show every answer in plain words; "Change" forgets one answer so it can be asked again.

## Helpers (assumptions are shown on screen; the buyer confirms the result)
- Budget from EMI: loan repaid by the monthly EMI over the chosen years at 9% a year, plus the down payment, rounded down to ₹50,000.
- Daily km from minutes to work: minutes one way at 20 km/h, doubled for there and back.

## Files
- Engine: `engine/app/questions.py`, route in `engine/app/main.py`, contracts `contracts/questions.*.schema.json`.
- Web: `web/app/find/page.tsx`, `web/components/chat/Helpers.tsx`, `web/lib/guided.ts`, `web/app/api/next-question/route.ts`.
- The old full form: `web/app/find/advanced/page.tsx`. The screens before it: `/start` (electric or not) and `/start/ev` (find or compare); comparison is `/compare` (see `docs/HOW_IT_WORKS.md` section 13).
- Tests: `engine/tests/test_questions.py`, `web/tests/guided.test.ts`, `web/tests/next-question-route.test.ts`.
  Web fixtures come from the engine: `python engine/scripts/make_web_fixtures.py`.
