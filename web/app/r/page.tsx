"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Header from "@/components/Header";
import PrintButton from "@/components/PrintButton";
import ResultView from "@/components/ResultView";
import { getVisitId, loadResult } from "@/lib/storage";
import type { Result } from "@/lib/types";

export default function ResultsPage() {
  const [state, setState] = useState<{ result: Result | null; visitId: string } | "loading">("loading");

  // The Result lives in sessionStorage, so a refresh does not lose it
  useEffect(() => {
    setState({ result: loadResult(), visitId: getVisitId() });
  }, []);

  const nav = (
    <>
      <Link
        href="/start"
        className="inline-flex min-h-11 items-center rounded-[10px] border border-[#4A5B66] px-4 py-2.5 text-sm font-semibold !text-white no-underline"
      >
        Edit my needs
      </Link>
      <PrintButton />
    </>
  );

  return (
    <>
      <Header>{state !== "loading" && state.result ? nav : null}</Header>
      {state === "loading" ? (
        <p className="mx-auto max-w-[720px] px-5 py-16 text-muted">Loading your shortlist&hellip;</p>
      ) : state.result ? (
        <ResultView result={state.result} visitId={state.visitId} />
      ) : (
        <main className="mx-auto flex max-w-[720px] flex-col items-start gap-5 px-5 py-16">
          <h1 className="m-0 text-2xl font-extrabold">No shortlist yet</h1>
          <p className="m-0 text-base text-muted">Tell us what you need and we&rsquo;ll build one.</p>
          <Link href="/start" className="inline-flex min-h-12 items-center rounded-xl bg-brand px-6 py-3 font-extrabold !text-white no-underline">
            Start
          </Link>
        </main>
      )}
    </>
  );
}
