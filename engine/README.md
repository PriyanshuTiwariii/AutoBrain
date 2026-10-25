# AutoBrain engine

The recommendation engine: pure, deterministic Python behind a small FastAPI service. No LLM call
happens in here. Rules for working on it are in `../AGENTS.md`.

## Run it (Windows, PowerShell)

First time only, from the repo root:

```powershell
cd engine
pip install -r requirements.txt
cd ..
copy .env.example .env
```

`.env` is never committed. The engine **refuses to start if `ENGINE_SECRET` is empty**, and logs a loud
warning while it is still `change-me`. Pick a real secret before the engine is reachable by anyone else.

Start the engine (from the repo root):

```powershell
cd engine
python -m uvicorn app.main:app --reload --port 8000
```

It validates the newest data release at startup (columns, keys, allowed values, SHA-256 checksums) and
stops if anything critical is wrong. It listens on `127.0.0.1:8000` only. Stop it with `Ctrl+C`.

Run the tests (from `engine/`): `python -m pytest`

## Try it in the browser, no code

1. Open <http://localhost:8000/docs>.
2. Click **Authorize**, paste your `ENGINE_SECRET`, click **Authorize**, then **Close**.
3. Open **POST /recommend** and click **Try it out**. A body is already filled in; the **Examples**
   drop-down has more.
4. Edit any value and click **Execute**. The Result is under **Server response**.
5. Pick the example "Bad input" to see the plain-English 422 message.

## Routes

| Route | Secret | What it does |
| --- | --- | --- |
| `GET /health` | no | `status`, `release`, row `counts` from the release's `manifest.json`, `engine_version` |
| `POST /recommend` | `X-Engine-Secret` header | Needs JSON in, Result JSON out |

**`/recommend` checks, in order:** the secret (missing and wrong both give 401, with the same message) →
the body is JSON → the Needs match `contracts/needs.schema.json` → the engine runs → the Result matches
`contracts/result.schema.json`.

- **Bad input is a 422** that names every problem, for example
  `{"detail": [{"field": "budget_max_inr", "message": "budget_max_inr must be a number of at least 300000"}]}`.
- **The engine never sends an invalid Result.** If one fails the schema, or the engine crashes, the caller
  gets a 500 with a generic message and the details go to the log.
- Every Result is logged with its release, row counts and engine version. The Needs are not logged.
- The same Needs always give the same Result, byte for byte.

## `result_id` is not a buyer ID

`result_id` is a hash of the Needs, the data release and the engine version. Identical inputs give the
same `result_id`, which is how a result is reproduced and compared. So **two different buyers with
identical Needs get the same `result_id`**.

**Note for the website (next step):** do not use `result_id` to identify, track or group buyers. The
website must create its **own random visit ID** for feedback (for example a UUID per visit), and send
`result_id` alongside it only to say which result was shown.

## CORS and the secret

CORS is **off by default**. For local development you can set `DEV_CORS=1` in `.env` to allow
`http://localhost:3000` (and nothing else) to call the engine from a browser; the engine logs a warning
when it is on. Leave it off otherwise.

The website must call `/recommend` from its **server routes** (Next.js route handlers), never from the
browser, so `ENGINE_SECRET` and the engine URL never reach a visitor. A secret sent from browser code
is not a secret.

## Not built yet

`/extract` and `/phrase` (the two LLM calls), variant and compare lookups, rate limits and request-size
caps. See `../docs/DESIGN.md`.
