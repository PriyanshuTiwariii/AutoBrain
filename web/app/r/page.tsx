"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import Header from "@/components/Header";
import PrintButton from "@/components/PrintButton";
import ResultView from "@/components/ResultView";
import { compareHref } from "@/lib/compare";
import { getVisitId, loadResult } from "@/lib/storage";
import type { Result } from "@/lib/types";

export default function ResultsPage() {
  const [state, setState] = useState<{ result: Result | null; visitId: string } | "loading">("loading");

  // The Result lives in sessionStorage, so a refresh does not lose it
  useEffect(() => {
    setState({ result: loadResult(), visitId: getVisitId() });
  }, []);

  const shortlisted =
    state !== "loading" && state.result
      ? [...new Set(state.result.slots.filter((s) => s.slot !== "not_recommended").map((s) => s.variant_key))].slice(0, 3)
      : [];

  const nav = (
    <>
      {shortlisted.length >= 2 ? (
        <Link href={compareHref(shortlisted)} className="btn btn-ghost !rounded-[10px]">
          Compare these cars
        </Link>
      ) : null}
      <Link
        href="/find?edit=1"
        className="btn btn-ghost !rounded-[10px]"
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
          <Link href="/start" className="btn btn-primary">
            Start
          </Link>
        </main>
      )}
    </>
  );
}
