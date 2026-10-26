# How AutoBrain works (in plain words)

AutoBrain gives honest, evidence-backed EV buying advice for Mahindra and Tata buyers in India.
The idea in one line: **a fixed, repeatable program picks the cars; an AI (optional) only helps read what the buyer typed.**

## 1. The big picture

```
Buyer  ->  Form (or "describe what you need" box)  ->  Needs  ->  Engine  ->  Result  ->  Results page
                        (AI optional)                  (JSON)   (plain Python)  (JSON)
```

- **Data:** every car fact comes from one place, the newest folder in `data/releases/` (87 variants, built from the master spreadsheet). Nothing is guessed, scraped or invented. At startup the engine checks the files (columns, allowed values, checksums) and refuses to start if they are wrong.
- **Engine:** the same input always gives the same output. There is no AI inside it.
- **AI:** used in at most two places, and never to rank, score, choose a car or supply a number. The whole flow works with the AI switched off.
- **Contracts:** `contracts/needs.schema.json` (input) and `contracts/result.schema.json` (output) define exactly what goes in and out.

## 2. What the buyer tells us (the "Needs")

| Input | Required? | What it does |
| --- | --- | --- |
| Budget (INR) | Yes | A hard limit. Includes the wall charger by default. |
| Seats needed | Yes | A hard limit (minimum seats). |
| Daily driving (km) | Yes | Used to judge whether the range is comfortable. |
| Home charging (yes / no / not sure) | Yes | Changes running costs, the charger cost, and how much DC fast-charging matters. |
| Longest regular trip (km) | No | Raises the range the car must comfortably cover. |
| Must-haves | No | Hard limits. A car without one is not recommended. |
| Nice-to-haves | No | A bonus in the score. Never rules a car out. |
| Priority (balanced, safety, cost, range, features, space) | No | Decides what the score rewards most. |
| Roads (city/highway, rough roads, light off-road) | No | Ranks cars by ground clearance, battery clearance and AWD. Never rules a car out. |
| Pricing (buy / battery financing / either) | No | BaaS rows are excluded unless the buyer asks for them. |
| Body types, excluded models | No | Narrow the list. |

Features available as must-have or nice-to-have: ADAS, 360 camera, sunroof, ventilated seats, ESP, all-wheel drive, 7 seats, lifetime battery warranty, crash-tested, charger included, adaptive suspension.

**The "describe what you need" box (AI call 1).** The buyer can type in their own words (English, Hindi or Hinglish). The AI only fills the form. The buyer sees every field and can change it before pressing the button. The text is treated as data, never as instructions. Every value is checked against the contract and anything invalid is dropped.

## 3. Step by step: what the engine does

### Step 1: Eligibility (a pass/fail gate)
Each variant is checked against the buyer's hard limits: pricing type, excluded models, body type, budget, seats and must-haves. Every check has **three** outcomes:

- **PASS:** the data confirms it.
- **FAIL:** the data says it does not have it. The car is out.
- **UNKNOWN:** the maker has not said. The car stays in, but it is flagged "not stated by maker, verify before buying".

Unknown is never treated as yes or no. One safety rule: a requirement of 6 or more seats can never pass on an unknown seat count.

### Step 2: Fit score (0 to 100, internal)
Cars that pass are scored on:

| Part | Max | Meaning |
| --- | --- | --- |
| Budget | 15 (25 if priority is cost) | Within budget gives a base amount plus a small bonus for headroom. Cheaper counts much more when the priority is cost. |
| Range | 25 | Tested range (or the maker's real-world figure) compared with daily km plus a 50% buffer, or the longest trip if that is bigger. |
| Nice-to-haves | 25 | The share of the buyer's nice-to-haves the car is confirmed to have. Neutral if none were chosen. |
| Priority | 25 | How well the car does on what the buyer said matters most (see below). |
| DC charging | up to 25 | Only when the buyer cannot charge at home. Slow chargers (under 40 kW average) score low and are pushed down the list. |
| Road conditions | up to 25 | Only for rough roads or light off-road (see section 4). |

What each priority rewards: **safety** (Bharat NCAP rating and adult score, ESP, ADAS, airbags), **cost** (lowest 5-year cost to own), **range** (longest tested range), **features** (ADAS, camera, sunroof, ventilated seats, adaptive suspension, terrain modes), **space** (7 seats, boot size, SUV body), **balanced** (a bit of all of these).

Only things the data confirms earn points. Unknown earns nothing, but it is never counted as a "no".

### Step 3: Evidence confidence (High / Medium / Low)
This is separate from fit. It says how much the data can be trusted for this car.

- **High:** price verified, range tested on the same model, and a clear crash-test status.
- **Medium:** the price is only corroborated, or the range test was on an earlier version of the car.
- **Low:** price pending, or no efficiency evidence.

### Step 4: Ranking
Cars are sorted by fit score, then confidence, then price (cheaper first). When the buyer cannot charge at home, slow-charging cars go below the rest.

### Step 5: Picking the cards (slots)
The buyer sees a few labelled cards, not a long list:

- **Best match:** the top-ranked car.
- **Same model, step up:** the next trim up from the best match, with the extra cost and what the buyer gains (only if it also qualifies).
- **Strong alternative:** the best-ranked car from a different model that has a real advantage over the top pick.
- **In between:** one price step down from the best match, with what the buyer gives up.
- **Don't overpay:** the cheapest car that still meets every need, and what it lacks.
- **Why not these:** near misses (slightly over budget or failing only one need), with the reason each failed.

Each card shows reasons, trade-offs and watch-outs, with the price status, efficiency basis and crash-test status next to the values they describe.

### Step 6: If nothing qualifies
The result says so plainly and explains why (for example "No variant within 8 lakh has 7 seats"). It shows the closest car and what the buyer would have to change (raise the budget, accept fewer seats, drop a must-have). If the only barrier is an unknown, it says "not confirmed", never "none has it".

## 4. Roads: rough roads and light off-road

This is how "I want a car for rough roads or off-roading" is handled.

- **Rough roads:** clearance under the car 15 points, clearance under the battery 5, adaptive suspension 5.
- **Light off-road:** clearance under the car 10, clearance under the battery 5, all-wheel drive 10.
- **Clearance bands:** 200 mm or more gets full credit, 180 to 199 mm partial, below that nothing. These bands are our own guideline, not a maker figure.
- **It only ranks, it never filters.** A car is not removed for low clearance.
- **Blank figures are shown as "not stated by maker"** and earn nothing. A stated low figure is shown separately as a trade-off ("Ground clearance 190 mm is on the low side for rough roads").
- **Light off-road adds a note:** no EV in our data is rated for serious off-roading.

## 5. Costs

- The budget check uses price plus wall charger by default.
- If the charger is not confirmed as included, the estimate is labelled "assumed, not confirmed".
- With no home charging, no wall charger is added, and running cost assumes mostly public DC charging.
- Electricity and 5-year costs are estimates: rounded to the nearest 1,000 and shown with "~". Official prices are shown exactly.
- BaaS (battery rental) prices are never compared with battery-included prices as if they were the same thing.

## 6. Where the AI is allowed (and where it is not)

| Allowed | Not allowed |
| --- | --- |
| Call 1: turn the buyer's text into form fields. | Ranking, scoring, or picking any car. |
| Call 2: put one car's fact sheet into friendly wording (never sees the buyer's raw text). | Supplying any number. Any number in AI text that is not in the engine's Result is thrown away and replaced by a template sentence. |

If the AI is off or fails, the form and the template sentences give the same recommendations.

## 7. Honesty rules shown to the buyer

- Blank or "Not stated" is always shown as "Not stated by maker".
- Price status, efficiency basis and crash-test status are always shown next to their values.
- Watch-outs are always shown with a recommended car (the wall-charger one is hidden for buyers with no home charging).
- A petrol or diesel crash rating is never applied to an EV.
- Accessories can fill a feature gap only if the data marks them usable, and never as equal to the higher trim. No aftermarket parts are suggested.
- Results are not tied to a person: the result ID is a hash of the needs, the data release and the engine version, so the same inputs give the same ID.

## 8. Where things live

| Folder | What it holds |
| --- | --- |
| `data/` | Master spreadsheet, the script that builds releases, and the release CSVs |
| `contracts/` | JSON schemas for input and output |
| `engine/app/` | The engine: `eligibility.py`, `scoring.py`, `terrain.py`, `slots.py`, `costs.py`, `nomatch.py`, `extract.py` |
| `web/` | The website: the form at `/start`, results at `/r`, PDF download and feedback link |
| `CHANGES.md` | The most up-to-date decisions (wins over other docs) |
