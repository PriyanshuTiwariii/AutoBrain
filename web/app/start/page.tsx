"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import Header from "@/components/Header";
import { BudgetHelper, CommuteHelper } from "@/components/chat/Helpers";
import { MAX_TEXT_CHARS, UNAVAILABLE, isExtractResponse } from "@/lib/extract";
import {
  applyPatch, chipsFor, formToPartial, isQuestionResponse, markAsked, mergeExtraction, removeField, toFormState,
  toRecommendNeeds,
} from "@/lib/guided";
import { getVisitId, loadForm, saveForm, saveResult } from "@/lib/storage";
import type { ExtractResponse, FieldProblem, NeedsInput, OptionalField, PartialNeeds, QuestionResponse, Result } from "@/lib/types";

const INPUT =
  "min-h-12 w-full rounded-xl border border-[#A9B6BF] bg-white px-3.5 py-2.5 text-base text-ink placeholder:text-[#7A8892] focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/30";
const PRIMARY = "btn btn-primary";
const SECONDARY = "btn btn-secondary";

const EXAMPLES = [
  "Family car for bad roads and daily office travel",
  "I'm 24, just got a job, office is 15 km away, budget around 12 lakh",
  "Family of 5, 18 lakh, we live in a flat with shared parking",
];

async function readTyped(text: string): Promise<ExtractResponse> {
  try {
    const reply = await fetch("/api/extract", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const body: unknown = await reply.json().catch(() => null);
    return reply.ok && isExtractResponse(body) ? body : UNAVAILABLE;
  } catch {
    return UNAVAILABLE;
  }
}

export default function StartPage() {
  const router = useRouter();
  const [needs, setNeeds] = useState<PartialNeeds>({});
  const [asked, setAsked] = useState<OptionalField[]>([]);
  const [question, setQuestion] = useState<QuestionResponse | null>(null);
  const [intro, setIntro] = useState("");
  const [typed, setTyped] = useState("");
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [helperOpen, setHelperOpen] = useState(false);
  const started = question !== null;
  const latest = useRef({ needs, asked });
  latest.current = { needs, asked };

  async function advance(nextNeeds: PartialNeeds, nextAsked: OptionalField[]) {
    setNeeds(nextNeeds);
    setAsked(nextAsked);
    setHelperOpen(false);
    setTyped("");
    setError(null);
    setBusy(true);
    try {
      const reply = await fetch("/api/next-question", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ needs: nextNeeds, asked: nextAsked }),
      });
      const body: unknown = await reply.json().catch(() => null);
      if (reply.ok && isQuestionResponse(body)) setQuestion(body);
      else setError("We could not get the next question. Please try again in a moment.");
    } catch {
      setError("We could not reach the server. Check your connection and try again.");
    } finally {
      setBusy(false);
    }
  }

  // Only "Edit my needs" (?edit=1) brings back earlier answers. A fresh visit always starts empty.
  useEffect(() => {
    getVisitId();
    if (new URLSearchParams(window.location.search).get("edit") !== "1") return;
    const before = formToPartial(loadForm());
    if (Object.keys(before).length > 0) void advance(before, []);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function describe() {
    const text = intro.trim();
    if (!text || busy) return;
    setBusy(true);
    setNote(null);
    const response = await readTyped(text);
    let merged = needs;
    if (response.status === "unavailable") {
      setNote("Typing isn't available right now. No problem: just answer a few quick questions.");
    } else if (response.status === "off_topic") {
      setNote(response.message);
    } else {
      merged = mergeExtraction(needs, response);
      if (Object.keys(merged).length === Object.keys(needs).length && JSON.stringify(merged) === JSON.stringify(needs)) {
        setNote(response.message ?? "We could not pick out any details, so let us ask you a few quick questions.");
      }
    }
    setIntro("");
    await advance(merged, asked);
  }

  function choose(patch: PartialNeeds) {
    if (!question || busy) return;
    void advance(applyPatch(needs, patch), markAsked(asked, question.field));
  }

  async function answerTyped() {
    const text = typed.trim();
    if (!text || !question?.field || busy) return;
    setBusy(true);
    setNote(null);
    const response = await readTyped(text);
    const merged = response.status === "unavailable" || response.status === "off_topic" ? needs : mergeExtraction(needs, response, question.field);
    if (JSON.stringify(merged) === JSON.stringify(needs)) {
      setBusy(false);
      setNote("We could not read that one. Please tap one of the options above.");
      return;
    }
    await advance(merged, markAsked(asked, question.field));
  }

  function forget(field: keyof NeedsInput) {
    void advance(removeField(needs, field), asked);
  }

  const showProblems = (problems: FieldProblem[]) => setError(problems.map((p) => p.message).join(" "));

  async function showShortlist() {
    const built = toRecommendNeeds(needs);
    if (!built.needs) {
      showProblems(built.problems);
      return;
    }
    setBusy(true);
    setError(null);
    saveForm(toFormState(needs));
    try {
      const response = await fetch("/api/recommend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(built.needs),
      });
      const body: unknown = await response.json().catch(() => null);
      if (response.ok && body && typeof body === "object" && "slots" in body) {
        saveResult(body as Result);
        router.push("/r");
        return;
      }
      const detail = (body as { detail?: FieldProblem[] } | null)?.detail;
      if (Array.isArray(detail) && detail.length) showProblems(detail);
      else setError("Something went wrong. Please try again.");
    } catch {
      setError("We could not reach the server. Check your connection and try again.");
    } finally {
      setBusy(false);
    }
  }

  const chips = chipsFor(needs);
  const finished = question?.done === true;

  return (
    <>
      <Header />
      <main className="mx-auto max-w-[720px] px-5 pb-24 pt-8 md:px-8 md:pt-12">
        <h1 className="m-0 mb-2 text-[28px] font-extrabold tracking-tight md:text-4xl">Let&apos;s find your car</h1>
        <p className="m-0 mb-6 text-base text-muted">
          No car knowledge needed. Tell us about your life and we will work out the rest. We only recommend cars the data can back up.
        </p>

        {chips.length > 0 ? (
          <section aria-label="What we understood" className="mb-6 rounded-2xl border border-line bg-surface p-4">
            <h2 className="m-0 mb-2 text-[15px] font-extrabold">What we understood so far</h2>
            <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
              {chips.map((c) => (
                <li key={c.field} className="flex items-center gap-2 rounded-full border border-line bg-white py-1.5 pl-3.5 pr-2 text-[14px]">
                  <span>
                    <span className="text-muted">{c.label}: </span>
                    <span className="font-bold">{c.value}</span>
                  </span>
                  <button
                    type="button"
                    onClick={() => forget(c.field)}
                    disabled={busy}
                    className="chip-btn min-h-8 rounded-full px-2.5 text-[13px] font-bold text-brand disabled:opacity-50"
                    aria-label={`Change ${c.label}`}
                  >
                    Change
                  </button>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {!started ? (
          <section aria-label="Tell us what you need" className="flex flex-col gap-3 rounded-[18px] border border-line bg-white p-5">
            <h2 className="m-0 text-lg font-extrabold">Tell us what you need</h2>
            <p className="m-0 text-[14px] text-muted">
              Write it your way, in English or Hinglish. Don&apos;t worry about car words. We will ask about anything we are missing.
            </p>
            <textarea
              aria-label="Tell us what you need"
              className={`${INPUT} min-h-28 resize-y`}
              placeholder="For example: I need an affordable family car for bad roads and daily office travel."
              maxLength={MAX_TEXT_CHARS}
              value={intro}
              onChange={(e) => setIntro(e.target.value)}
            />
            <div className="flex flex-wrap gap-2" aria-label="Examples">
              {EXAMPLES.map((e) => (
                <button
                  key={e}
                  type="button"
                  onClick={() => setIntro(e)}
                  className="chip-btn min-h-10 rounded-full border border-line bg-surface px-3.5 py-2 text-left text-[13px]"
                >
                  {e}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <button type="button" onClick={describe} disabled={busy || intro.trim() === ""} aria-busy={busy} className={PRIMARY}>
                {busy ? "Reading…" : "Continue"}
              </button>
              <button type="button" onClick={() => void advance(needs, asked)} disabled={busy} className={SECONDARY}>
                I&apos;d rather answer questions
              </button>
            </div>
            <span className="text-[13px] text-muted">Your message is not saved.</span>
          </section>
        ) : null}

        {note ? (
          <div role="status" className="mb-4 mt-4 rounded-xl border border-line bg-surface p-3.5 text-[15px] leading-relaxed">
            {note}
          </div>
        ) : null}

        {started && question && !finished ? (
          <section aria-label="Next question" className="flex flex-col gap-4 rounded-[18px] border border-line bg-white p-5">
            <div>
              <h2 className="m-0 text-xl font-extrabold">{question.question}</h2>
              {question.why ? <p className="m-0 mt-1 text-[14px] text-muted">{question.why}</p> : null}
              {question.kind === "optional" ? (
                <p className="m-0 mt-1 text-[13px] font-semibold text-brand">Optional: this one changes which cars we show first.</p>
              ) : null}
            </div>

            <div className="grid gap-2 sm:grid-cols-2">
              {question.cards.map((card) => (
                <button
                  key={card.id}
                  type="button"
                  disabled={busy}
                  onClick={() => choose(card.patch)}
                  className="choice-card flex min-h-14 flex-col justify-center rounded-xl border border-line bg-white px-4 py-3 text-left"
                >
                  <span className="text-[16px] font-bold">{card.label}</span>
                  {card.sublabel ? <span className="text-[13px] text-muted">{card.sublabel}</span> : null}
                </button>
              ))}
            </div>

            {question.helper ? (
              <div className="flex flex-col gap-3">
                <button type="button" onClick={() => setHelperOpen((o) => !o)} className="self-start text-[15px] font-bold text-brand underline">
                  {helperOpen ? "Hide the helper" : question.helper === "budget_emi" ? "I don't know. Help me decide" : "I'm not sure. Help me work it out"}
                </button>
                {helperOpen && question.helper === "budget_emi" ? (
                  <BudgetHelper onUse={(inr) => choose({ budget_max_inr: inr })} />
                ) : null}
                {helperOpen && question.helper === "commute_minutes" ? (
                  <CommuteHelper onUse={(km) => choose({ daily_km: km })} />
                ) : null}
              </div>
            ) : null}

            <div className="flex flex-col gap-2">
              <label htmlFor="typed" className="text-[14px] font-bold">Or type it your way</label>
              <div className="flex flex-col gap-2 sm:flex-row">
                <input
                  id="typed"
                  className={INPUT}
                  placeholder={question.example ?? ""}
                  maxLength={MAX_TEXT_CHARS}
                  value={typed}
                  onChange={(e) => setTyped(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") void answerTyped();
                  }}
                />
                <button type="button" onClick={answerTyped} disabled={busy || typed.trim() === ""} aria-busy={busy} className={SECONDARY}>
                  Send
                </button>
              </div>
            </div>
          </section>
        ) : null}

        {started && finished ? (
          <section aria-label="Ready" className="flex flex-col gap-3 rounded-[18px] border border-good/30 bg-good-bg p-5">
            <h2 className="m-0 text-xl font-extrabold text-good-ink">That&apos;s all we need</h2>
            <p className="m-0 text-[15px] text-good-ink">
              Check what we understood above. Change anything that is wrong, then see your shortlist.
            </p>
          </section>
        ) : null}

        {error ? (
          <div role="alert" className="mt-4 rounded-xl border border-warn-line bg-warn-bg p-4 text-[15px] font-semibold text-warn-ink">
            {error}
          </div>
        ) : null}

        {started && question?.can_show_results ? (
          <div className="sticky-cta mt-6 flex flex-col gap-2">
            <button type="button" onClick={showShortlist} disabled={busy} aria-busy={busy} className={`${finished ? PRIMARY : SECONDARY} w-full shadow-lg`}>
              {busy ? "Finding your shortlist…" : finished ? "Show my shortlist" : "Skip the rest, show my shortlist now"}
            </button>
            {!finished && question.missing_required.length > 0 ? (
              <span className="text-[13px] text-muted">
                We have not asked about parking yet. Costs will assume you can charge at home, and the results will say so.
              </span>
            ) : null}
          </div>
        ) : null}

        <p className="mt-10 text-[14px] text-muted">
          Know your cars already?{" "}
          <Link href="/start/advanced" className="font-bold">
            Show me all the options
          </Link>
        </p>
      </main>
    </>
  );
}
