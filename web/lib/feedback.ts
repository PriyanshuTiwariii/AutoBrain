export interface FeedbackContext {
  /** Random per visit; made by the website. Never the engine's result_id. */
  visitId: string;
  /** Which result was shown. Says nothing about who saw it. */
  resultId: string;
  datasetVersion: string;
  /** variant_key of the top pick, if there was one. */
  topPick: string | null;
}

/**
 * Google Form entry IDs (the number in entry.123456789), if the form has prefilled fields.
 * Without them the details are still added to the link under plain names.
 */
export interface FeedbackEntryIds {
  visit?: string;
  result?: string;
  dataset?: string;
  topPick?: string;
}

/** The feedback form link with the visit and result details attached, or null if no form is set up. */
export function buildFeedbackUrl(
  baseUrl: string | undefined,
  context: FeedbackContext,
  entryIds: FeedbackEntryIds = {},
): string | null {
  const base = (baseUrl ?? "").trim();
  if (!base) return null;
  let url: URL;
  try {
    url = new URL(base);
  } catch {
    return null;
  }
  const field = (entryId: string | undefined, plainName: string) =>
    entryId && entryId.trim() ? `entry.${entryId.trim()}` : plainName;

  const values: [string, string][] = [
    [field(entryIds.visit, "visit_id"), context.visitId],
    [field(entryIds.result, "result_id"), context.resultId],
    [field(entryIds.dataset, "dataset_version"), context.datasetVersion],
  ];
  if (context.topPick) values.push([field(entryIds.topPick, "top_pick"), context.topPick]);

  if (Object.values(entryIds).some((id) => id && id.trim())) url.searchParams.set("usp", "pp_url");
  for (const [name, value] of values) url.searchParams.set(name, value);
  return url.toString();
}
