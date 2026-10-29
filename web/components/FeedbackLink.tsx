"use client";

import { buildFeedbackUrl } from "@/lib/feedback";
import type { Result } from "@/lib/types";

/** Link to the feedback form, prefilled with this visit's random ID, the result and the top pick. */
export default function FeedbackLink({ result, visitId }: { result: Result; visitId: string }) {
  // Literal process.env.NEXT_PUBLIC_* names so Next can inline them into the browser bundle
  const url = buildFeedbackUrl(
    process.env.NEXT_PUBLIC_FEEDBACK_FORM_URL,
    {
      visitId,
      resultId: result.result_id,
      datasetVersion: result.dataset_version,
      topPick: result.slots.find((s) => s.slot === "best_match")?.variant_key ?? null,
    },
    {
      visit: process.env.NEXT_PUBLIC_FEEDBACK_ENTRY_VISIT,
      result: process.env.NEXT_PUBLIC_FEEDBACK_ENTRY_RESULT,
      dataset: process.env.NEXT_PUBLIC_FEEDBACK_ENTRY_DATASET,
      topPick: process.env.NEXT_PUBLIC_FEEDBACK_ENTRY_TOPPICK,
    },
  );

  if (!url) {
    return (
      <p className="text-sm text-muted print:hidden">
        Feedback link not set up yet: add NEXT_PUBLIC_FEEDBACK_FORM_URL to the .env file.
      </p>
    );
  }
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="btn btn-light print:hidden"
    >
      Tell us if this helped
    </a>
  );
}
