"use client";

import { useState } from "react";
import { MAX_TEXT_CHARS, UNAVAILABLE, isExtractResponse, noteFor, type Applied, type Note } from "@/lib/extract";
import type { ExtractResponse, FieldProblem } from "@/lib/types";

const TONE: Record<Note["tone"], string> = {
  ok: "border-good/30 bg-good-bg text-good-ink",
  info: "border-line bg-surface text-ink",
  warn: "border-warn-line bg-warn-bg text-warn-ink",
};

export const EXAMPLE_TEXT = "For example: Budget 15 lakh, family of 4, I drive about 40 km a day and can charge at home.";

/**
 * "Describe what you need". Sends the text to the server route, then hands the answer to the page, which
 * puts it in the form. It never submits anything: the buyer still sees and can change every field.
 * With no key, or OpenAI down, it shows a short note and the form works as it always did.
 */
export default function DescribeBox({ onApply }: { onApply: (response: ExtractResponse) => Applied }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<Note | null>(null);

  async function describe() {
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    setBusy(true);
    setNote(null);
    let response: ExtractResponse = UNAVAILABLE;
    try {
      const reply = await fetch("/api/extract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: trimmed }),
      });
      const body: unknown = await reply.json().catch(() => null);
      if (reply.ok && isExtractResponse(body)) {
        response = body;
      } else if (reply.status === 422) {
        const detail = (body as { detail?: FieldProblem[] } | null)?.detail;
        setNote({ tone: "info", lines: [detail?.[0]?.message ?? "We could not use that message. Please shorten it or use the form."] });
        setBusy(false);
        return;
      }
    } catch {
      /* the network is down: same short note as when OpenAI is down */
    }
    setNote(noteFor(response, onApply(response)));
    setBusy(false);
  }

  return (
    <section aria-label="Describe what you need" className="mb-8 flex flex-col gap-3 rounded-[18px] border border-line bg-white p-5">
      <h2 className="m-0 text-lg font-extrabold">Describe what you need</h2>
      <p className="m-0 text-[14px] text-muted">
        Write it in your own words, in English or Hinglish. We fill in the form below; you check it and change anything before you
        press the button.
      </p>
      <textarea
        aria-label="Describe what you need"
        className="min-h-28 w-full resize-y rounded-xl border border-[#A9B6BF] bg-white px-3.5 py-2.5 text-base text-ink placeholder:text-[#7A8892] focus:border-brand focus:outline-none focus:ring-2 focus:ring-brand/30"
        placeholder={EXAMPLE_TEXT}
        maxLength={MAX_TEXT_CHARS}
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={describe}
          disabled={busy || text.trim() === ""}
          aria-busy={busy}
          className="btn btn-secondary"
        >
          {busy ? "Reading…" : "Fill in the form for me"}
        </button>
        <span className="text-[13px] text-muted">Your message is not saved.</span>
      </div>
      <div aria-live="polite">
        {note ? (
          <div className={`flex flex-col gap-1.5 rounded-xl border p-3.5 text-[15px] leading-relaxed ${TONE[note.tone]}`}>
            {note.lines.map((line) => (
              <p key={line} className="m-0">
                {line}
              </p>
            ))}
          </div>
        ) : null}
      </div>
    </section>
  );
}
