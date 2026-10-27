# How AutoBrain works (in plain words)

AutoBrain gives honest, evidence-backed EV buying advice for Mahindra and Tata buyers in India.
The idea in one line: **a fixed, repeatable program picks the cars; an AI (optional) only helps read what the buyer typed.**

## 1. The big picture

```
Buyer  ->  Own words + easy follow-up questions (or the full form)  ->  Needs  ->  Engine  ->  Result  ->  Results page
                  (AI optional, only reads text)                        (JSON)   (plain Python)  (JSON)
```

The buyer is not expected to know car terms. They describe their life ("family of four, bad roads, office 15 km away"), and the system asks a few easy questions until it has the four things the engine cannot work without. Section 9 explains this, section 10 lists every assumption, and section 11 walks one buyer through the whole thing.

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

**How the buyer gives these (guided intake).** The main page, `/start`, does not show this table as a form. It asks life questions and turns the answers into these fields (section 9). The old full form is still at `/start/advanced` for people who know cars.

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
| `engine/app/` | The engine: `eligibility.py`, `scoring.py`, `terrain.py`, `slots.py`, `costs.py`, `nomatch.py`, `extract.py`, `questions.py` (which follow-up to ask) |
| `web/` | The website: guided questions at `/start`, full form at `/start/advanced`, results at `/r`, PDF download and feedback link |
| `docs/GUIDED_FLOW.md` | Short technical note on the guided intake |
| `CHANGES.md` | The most up-to-date decisions (wins over other docs) |

## 9. The guided intake (how a first-time buyer gets from "I know nothing" to a shortlist)

**The problem it solves.** A form that asks for "ADAS", "AWD" or "ground clearance" sends a new buyer to Google, and then we are no better than a spec sheet. So we ask things a person can answer from their own life, and our code translates the answers into the fields the engine needs.

**The loop**

1. The buyer types a few words (optional): "I need an affordable family car for bad roads and daily office travel." The AI reads it (call 1) and fills in only what was clearly said. Here: bad roads. It does not invent a budget, a seat count or a distance.
2. The engine's `/next_question` looks at what is known and picks ONE next question.
3. The buyer taps a card (or types, or uses a helper). The answer is stored as Needs fields. Go back to step 2.
4. When budget, seats and daily km are known, "Show my shortlist" appears. The buyer can stop before the optional questions.
5. The normal engine builds the shortlist. Nothing about the engine's ranking changed.

**Which question comes next**

- **Required, always in this order:** budget, seats, daily driving, home charging. Anything already known is skipped.
- **Optional (roads, what matters most, long trips):** asked only when the possible answers would change the shortlist. The engine tries each plausible answer, looks at the top 3 cars each time, and asks only if the best match changes or at least 2 of the top 3 change. At most 3 optional questions, and never the same one twice.
- Question text and answer cards are fixed templates in `engine/app/questions.py`. The AI never writes a question, so a buyer's typed text cannot steer it.

**What each question maps to**

| Question | Cards | Becomes |
| --- | --- | --- |
| What is the most you want to spend? | Up to 10 / 10-15 / 15-20 / 20-30 / more than 30 lakh | Budget cap of 10, 15, 20, 30 or 50 lakh |
| Who rides with you most days? | Me or me + partner / small family / family with parents / big family | Seats 2 / 4 / 5 / 7 |
| How far do you drive on a normal day? | Office up to 10 km / 10-20 / 20-35 km away; drive all day; only short trips | Daily km 20 / 40 / 70 / 150 / 15 (office distance is counted there and back) |
| Where will the car sleep at night? | Own house with parking / apartment with own spot / shared or street parking / not sure | Home charging: yes / unsure / no / unsure |
| What are your roads like? (optional) | Smooth / potholes and speed breakers / hills, gravel, village | Roads: city_highway / rough_roads / light_offroad |
| What worries you most? (optional) | Safety / running cost / going far / premium feel / space / a bit of everything | Priority: safety / cost / range / features / space / balanced |
| Regular long trips? (optional) | Never / monthly about 150, 300 or 500 km | Longest regular trip, or nothing |

**Rules that protect trust**

- Budget, seats and daily km are never filled in for the buyer. Home charging not yet answered is sent as "not sure".
- "Not sure" stays unknown. On optional questions it sets nothing at all.
- A situation answer never creates a must-have. Must-haves are hard filters, and a guess would wrongly empty the shortlist. Must-haves come only from what the buyer says themselves.
- The "What we understood so far" strip shows every answer in plain words. "Change" forgets that one answer; a forgotten required answer is simply asked again. Nothing stale is kept.
- With the AI off, the same questions run one by one without the typing box.

**Two small helpers (shown only when the buyer does not know the number)**

- *Budget from EMI:* monthly EMI, loan years, down payment and interest rate. We work out the loan that EMI repays and add the down payment. The interest rate starts at 9% and is editable. It is a rough estimate, not a loan offer.
- *Daily km from commute time:* minutes one way and average speed, doubled for the way back. The speed starts at 20 km/h and is editable. It counts only that trip.
- In both, the buyer sees the assumptions and the working, and must press "Use" before the number becomes a requirement.

**"Not sure" about home charging.** An apartment with your own parking does not mean the society or the wiring allows a charger, so that card is stored as "not sure", not "yes". The engine then costs the car as if a home charger exists (the cheaper case) and says so in the results notes, with the charger cost labelled "assumed". It does not hide this.

## 10. Every assumption in one place

These are choices we made, not facts. All are shown to the buyer where they matter.

| Area | Assumption | Where it lives |
| --- | --- | --- |
| Car data | Only the newest folder in `data/releases/` (currently 2026-10-25-r2). Prices are ex-showroom as of the release date. | `data/` |
| Budget | Includes the wall charger unless the buyer says otherwise. | `costs.py` |
| Electricity price | Home 8 rupees per kWh, public DC 22 rupees per kWh. | `costs.py`, master sheet Assumptions tab |
| Charging mix | With home charging: 90% home, 10% public DC. Without: 10% home, 90% public DC. "Not sure" uses the home mix and is labelled. | `costs.py` |
| Ownership period | 5 years. The 5-year cost covers car price, charger and electricity only. It excludes insurance, financing, maintenance and resale. | `costs.py` |
| Estimate rounding | Electricity and 5-year cost are rounded to the nearest 1,000 and shown with "~". | `costs.py` |
| Range need | Daily km plus a 50% buffer (real driving uses more than the ideal figure), or the longest regular trip if bigger. | `scoring.py` |
| Slow DC charging | Under 40 kW average counts as slow and scores low. Only matters when the buyer cannot charge at home. | `scoring.py` |
| Ground clearance | 200 mm or more gets full credit, 180 to 199 partial, below that none. Our own guideline, not a maker figure. Ranks only, never removes a car. | `terrain.py` |
| Unknown data | Blank or "Not stated" is unknown, never yes or no, and is shown as "Not stated by maker". | whole engine |
| Pricing | Battery-included purchase by default. Battery rental (BaaS) rows are excluded unless asked for. | `eligibility.py` |
| Optional follow-up | Asked only when it changes the best match or 2 of the top 3 cars (score 1.5). A starting guess, to be checked against real buyers. Max 3. | `questions.py` |
| Budget chips | A chip means "up to" its upper limit (the top chip means up to 50 lakh). | `questions.py` |
| Seat chips | 2 / 4 / 5 / 7 minimum seats. | `questions.py` |
| Distance chips | Office up to 10 / 10-20 / 20-35 km one way become 20 / 40 / 70 daily km; "all day" is 150; "short trips" is 15. | `questions.py` |
| EMI helper | 9% a year interest (editable), loan rounded down to the nearest 50,000 after adding the down payment. Estimate only. | `web/lib/guided.ts` |
| Commute helper | 20 km/h average (editable), there and back only. | `web/lib/guided.ts` |
| Not sure about charging | Costed as if a home charger exists, with a note. Never treated as a confirmed yes. | `costs.py`, `slots.py` |
| The AI | Reads text and explains one car at a time. Never ranks, scores or supplies a number. Numbers in AI text that are not in the Result are discarded. | `extract.py`, `explain.py` |
| Privacy | The typed message is not saved or logged. Phone numbers are never logged. | web routes, `extract.py` |

## 11. End to end: one buyer, start to finish

Meet Rohan, 24, first job, flat with street parking, office 15 km away, has never bought a car.

1. He opens `/start` and types: "Need a family car for bad roads, office is 15 km away. Budget around 12 lakh."
2. The AI (call 1) reads it. The engine validates every field and keeps only what is allowed: budget 12 lakh, roads rough, daily km 30 (15 km each way, doubled by our code). "Family" gives no number, so seats stay empty.
3. `/next_question` sees seats are missing and asks "Who rides with you on most days?" He taps "A small family" (4 seats).
4. Next it asks "Where will the car sleep at night?" He taps "Shared or street parking" (no home charging).
5. Budget, seats, daily km and charging are known. The engine checks whether "what worries you most" or "long trips" would change the top 3. If priority would, it asks once. He picks "Keeping my family safe".
6. The page shows "What we understood": up to 12 lakh, 4 seats, about 30 km a day, cannot charge at home, rough roads, safety first. He can change any line.
7. He presses "Show my shortlist". The engine checks every car against his hard limits (budget, seats), ranks the rest on range, charging, roads and safety, and builds the cards: best match, step up, alternative, in between, don't overpay, why not these.
8. Each card shows reasons, trade-offs and watch-outs, with price status, efficiency basis and crash-test status next to the numbers they describe. Anything the maker has not stated says "Not stated by maker". The AI, if on, only rewords one car's facts and cannot add a number.
9. If he changes his mind ("actually my budget is 8 lakh"), he presses "Change" on the budget line, answers again, and gets a fresh shortlist built from the new needs only.

## 12. Explaining it in two minutes

- **The promise:** honest, evidence-backed EV advice for Mahindra and Tata buyers who know nothing about cars. Trust is the product.
- **The data:** one release of 87 variants, built from a master spreadsheet with sources. Nothing is guessed or scraped.
- **The brain:** a plain Python engine. Same input, same output, no AI. It has three layers: can the car qualify (pass, fail or unknown), how well does it fit (score), and how much can we trust the data (confidence).
- **The AI's job:** read the buyer's own words, and reword one car's facts. It never picks a car and never supplies a number. Switch it off and everything still works.
- **The new part:** instead of a spec form, a short conversation. The engine, not the AI, decides which question is worth asking, by checking whether the answer would change the shortlist.
- **Honesty:** unknown stays unknown, every estimate shows its assumptions, and the page says plainly what we could not confirm.
- **What is still a guess:** the 9% loan rate, the 20 km/h commute speed, and the 1.5 "worth asking" threshold. Each is visible and adjustable, and the threshold needs testing with real buyers.
