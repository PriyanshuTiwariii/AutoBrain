"use client";

import Link from "next/link";
import { useState } from "react";
import Header from "@/components/Header";
import OptionCard from "@/components/OptionCard";

const BoltIcon = (
  <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M13 2 4 14h7l-1 8 9-12h-7z" />
  </svg>
);
const FuelIcon = (
  <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M4 22V4a2 2 0 0 1 2-2h6a2 2 0 0 1 2 2v18M3 22h12M14 10h2a2 2 0 0 1 2 2v3a2 2 0 0 0 4 0V8l-3-3" />
    <path d="M7 8h4" />
  </svg>
);

/** First question: electric or not. Only electric is available today; the other says so plainly. */
export default function StartPage() {
  const [nonEv, setNonEv] = useState(false);

  return (
    <>
      <Header />
      <main className="mx-auto max-w-[720px] px-5 pb-20 pt-8 md:px-8 md:pt-12">
        <Link href="/" className="mb-4 inline-block text-[15px] font-bold">
          &larr; Home
        </Link>
        <h1 className="m-0 mb-2 text-[28px] font-extrabold tracking-tight md:text-4xl">What kind of car are you looking at?</h1>
        <p className="m-0 mb-8 text-base text-muted">Pick one to begin. You can always come back.</p>

        <div className="grid gap-4 sm:grid-cols-2">
          <OptionCard
            title="Electric car (EV)"
            description="Find the right EV for you, or compare EVs you have already shortlisted."
            icon={BoltIcon}
            href="/start/ev"
          />
          <OptionCard
            title="Petrol or diesel"
            description="Not covered yet."
            icon={FuelIcon}
            badge="Coming later"
            onClick={() => setNonEv((v) => !v)}
            selected={nonEv}
          />
        </div>

        {nonEv ? (
          <div role="status" className="mt-5 rounded-xl border border-line bg-surface p-4 text-[15px] leading-relaxed">
            We only give advice on electric cars for now. Petrol and diesel advice is not available yet, and we would rather say so than
            guess. If you are open to an electric car, it takes about a minute to find out which ones suit you.
            <div className="mt-3">
              <Link href="/start/ev" className="btn btn-primary">
                Look at electric cars
              </Link>
            </div>
          </div>
        ) : null}
      </main>
    </>
  );
}
