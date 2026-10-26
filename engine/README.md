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
| `POST /extract` | `X-Engine-Secret` header | The buyer's own words in, the Needs fields read from them out (uses the language model) |

**`/recommend` checks, in order:** the secret (missing and wrong both give 401, with the same message) →
the body is JSON → the Needs match `contracts/needs.schema.json` → the engine runs → the Result matches
`contracts/result.schema.json`.

- **Bad input is a 422** that names every problem, for example
  `{"detail": [{"field": "budget_max_inr", "message": "budget_max_inr must be a number of at least 300000"}]}`.
- **The engine never sends an invalid Result.** If one fails the schema, or the engine crashes, the caller
  gets a 500 with a generic message and the details go to the log.
- Every Result is logged with its release, row counts and engine version. The Needs are not logged.
- The same Needs always give the same Result, byte for byte.

## `POST /extract`: "Describe what you need"

The buyer's own words go in (`{"text": "..."}`, 1 to 1,500 characters); the Needs fields that could be read come
out (`contracts/extract.response.schema.json`). The website uses it to fill in the form; the buyer still checks
and changes every field.

```json
{"status": "read", "complete": false,
 "needs": {"seats_min": 4, "home_charging": "yes"},
 "missing": ["budget_max_inr", "daily_km"],
 "question": "What is your budget? For example, 15 lakh.",
 "source": "primary", "message": null}
```

- `status`: `read` (the answer was used), `partial` (both models gave some unusable fields; only the valid ones are
  returned and `message` names the rest), `off_topic`, or `unavailable` (no key, OpenAI down, or both models
  failed). `unavailable` is a normal 200 answer, not an error: the form keeps working.
- **At most one `question`**, only about a missing budget, seats, daily km or home charging, chosen from fixed
  wording in the code (never model-written text).
- **The model reads facts; the engine does the arithmetic.** It reports "15" and "lakh", or "25 km" and "each
  way"; the engine multiplies. Indian amounts (15 lakh, 15L, 1.5 crore, ₹12,50,000), Hinglish, "family of 4" and
  "office 25 km each way" (= 50 km a day) are covered.
- **Every field is checked against `contracts/needs.schema.json`**, and one that fails is dropped, never passed on.
  Features, priorities and car names are limited to the contract's and the data's own lists.
- **If the first model's answer is not usable, the second model is tried once.** If that fails too, the fields that
  could be read are returned.
- **The buyer's text is data, never instructions.** It goes in the user message inside tags, never in the
  instructions; the model can only answer in a fixed JSON shape; "ignore your rules" changes nothing.
- **The buyer's text is never logged.** The log says which model answered, the reasoning effort, the outcome and the
  time, for example `extract attempt: role=primary model=... effort=none outcome=ok latency_ms=1900`.

### Settings (`.env`)

| Variable | Meaning |
| --- | --- |
| `LLM_PROVIDER` | `openai` (the only one; also the default when the line is missing) |
| `OPENAI_API_KEY` | The key. Empty = the box shows a short note and the form works as usual |
| `LLM_MODEL_PRIMARY`, `LLM_MODEL_FALLBACK` | Model names, exactly as OpenAI names them. **No model name is in the code** |
| `LLM_PRIMARY_REASONING_EFFORT` | Default `none` |
| `LLM_FALLBACK_REASONING_EFFORT` | Default `low` (some models do not accept `none`) |
| `LLM_TIMEOUT_SECONDS` | Per model, default 15 |

It uses OpenAI's Responses API with Structured Outputs (strict JSON schema) and does not store the text on
OpenAI's side (`store=False`).

**A variable in your computer's environment beats `.env`.** If a Windows environment variable named
`OPENAI_API_KEY` exists, it is used instead of the key in `.env`, and OpenAI answers 401 if it is an old key.
The engine warns at startup, naming the variable (never its value), and says so in the log when OpenAI rejects a key.

### Trying it against the real OpenAI API

```powershell
cd engine
python scripts/try_extract.py --runs 2
```

Runs about twenty made-up buyer messages (English, Hinglish, crore, injection, off-topic) through the primary
model at effort `none`, at `low`, and through the fallback model, and prints how often each answer was valid and
read as expected. It makes real, very small API calls with your key. Use it after changing a model name.

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

`/phrase` (the second LLM call: wording the reasons), variant and compare lookups, rate limits and
request-size caps. See `../docs/DESIGN.md`.
