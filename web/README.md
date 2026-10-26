# AutoBrain website (demo)

Next.js 14 (App Router), TypeScript, Tailwind. Mobile-first: built for a 390px phone, fine on a desktop.

| Page | What it does |
| --- | --- |
| `/` | One line and a Start button |
| `/start` | "Describe what you need" box (optional), then the needs form: budget (lakh), seats, daily km, longest trip (optional), home charging, must-haves, nice-to-haves, priority |
| `/r` | The results page: every card the engine returns, watch-outs, price status labels, side-by-side table, disclaimer, "Download as PDF", feedback link |
| `/api/recommend` | Server route. The form posts here; it calls the engine with the secret |
| `/api/extract` | Server route for the Describe box; it calls the engine's `/extract` the same way |

## How it fits together

```
browser ──► website (localhost:3000) ──server route──► engine (localhost:8000)
                                       adds X-Engine-Secret
```

- The browser only ever talks to the website. The engine's address and `ENGINE_SECRET` live in the website's
  **server** code and are never sent to the browser (a test checks this).
- Every number on the results page comes from the engine's Result JSON. The page formats numbers (₹6.99 lakh)
  and never calculates one; a test fails if the page shows a number that is not in the Result.
- The Result is kept in the browser's `sessionStorage`, so a refresh does not lose it.

## Run the engine and the website together (Windows)

You need Python 3.12+ and Node 20+ (check with `python --version` and `node --version`).

### One-time setup (PowerShell, from the repo root)

```powershell
copy .env.example .env
```

Open `.env` and set `ENGINE_SECRET` to any private phrase that is not `change-me`. The engine and the website
both read this one file, so they always agree on the secret.

```powershell
cd engine
pip install -r requirements.txt
cd ..\web
npm install
cd ..
```

### Every time: two terminals

**Terminal 1, the engine** (leave it running):

```powershell
cd engine
python -m uvicorn app.main:app --port 8000
```

Wait for `Application startup complete.`

**Terminal 2, the website** (leave it running):

```powershell
cd web
npm run dev
```

Wait for `Ready`, then open **http://localhost:3000** in your browser and press **Start**.

To stop either one, click its terminal and press `Ctrl+C`.

### If something goes wrong

| What you see | What it means |
| --- | --- |
| `only one usage of each socket address` when starting the engine | The engine is already running on port 8000. Use that one. |
| The form says "The advice engine isn't reachable" | The engine (Terminal 1) is not running, or `ENGINE_URL` in `.env` is wrong. |
| "The website is not set up correctly yet" | `ENGINE_SECRET` is missing from `.env`, or it differs from the one the running engine started with. Fix `.env`, then restart **both** terminals. |
| You changed `.env` and nothing changed | `.env` is read when a program starts. Press `Ctrl+C` and start it again. |

## "Describe what you need"

A text box above the form. The buyer writes in their own words (English or Hinglish: "Mera budget 12 lakh tak hai,
5 seater, office 25 km door, ghar pe charging nahi hai"), presses **Fill in the form for me**, and the form below is
filled in.

- **It only fills in the form.** Nothing is submitted. The note says what was filled in and to check every
  field; the buyer changes anything, then presses **Show my shortlist** as usual. What the buyer typed in other
  fields stays, even if they keep typing while the answer is on its way.
- **At most one question** ("One more thing: What is your budget?"), only when the budget, seats, daily km or home
  charging is missing.
- **Things the form has no input for** (body type, excluded cars, battery financing) are reported as "heard but not
  applied", never silently dropped.
- **With no key, or OpenAI down,** the box shows a short note ("Describing your needs isn't available right now.
  Please fill in the form below.") and the form works exactly as before.
- **The message is not saved:** not in the browser's storage, not in the server's logs.

The language model runs in the engine; the website never sees the OpenAI key. See `engine/README.md` for the
settings.

## Download as PDF

The button opens the browser's print dialog. Choose **Save as PDF** as the destination. The print layout hides
the buttons and keeps each card on one page.

## Feedback link

Set `NEXT_PUBLIC_FEEDBACK_FORM_URL` in `.env` to your Google Form. The link carries:

- a **random visit ID**, created by the website for each visit (never the engine's `result_id`, which says
  nothing about who someone is),
- the `result_id`, the data release and the top pick's `variant_key`.

For a Google Form with prefilled fields, put the field numbers in the `NEXT_PUBLIC_FEEDBACK_ENTRY_*` variables
(see `.env.example`). Without them the details are added as plain query values. With no URL set, the page says
the link is not set up yet.

## Tests

```powershell
cd web
npm test            # unit and page tests
npm run typecheck   # TypeScript, strict
```

The page tests render real Results, and the Describe box tests use real `/extract` responses, produced by the
engine (`tests/fixtures/`; the model is scripted, so no network). To regenerate them after an engine change, from
`engine/`:

```powershell
python scripts/make_web_fixtures.py
```

## Known limits

- Next.js 14 is the version the project asked for. `npm audit` reports advisories on it (mostly
  denial-of-service) that are fixed only in newer major versions. Fine for local demos; upgrade before the site
  is reachable by the public.
- No test-drive or quote buttons, no accounts, no chat: not part of the demo.
