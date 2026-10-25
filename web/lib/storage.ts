import { EMPTY_FORM, type FormState } from "./needs";
import type { Result } from "./types";

const KEYS = {
  visit: "autobrain:visit",
  form: "autobrain:form",
  result: "autobrain:result",
} as const;

// sessionStorage can be missing or throw (private windows, blocked storage): never let that break a page.
function read(key: string): string | null {
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string): void {
  try {
    window.sessionStorage.setItem(key, value);
  } catch {
    /* the page still works; a refresh just won't restore it */
  }
}

/** A random ID for this visit. It is NOT the engine's result_id, and it identifies nobody. */
export function newVisitId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

export function getVisitId(): string {
  const existing = read(KEYS.visit);
  if (existing) return existing;
  const fresh = newVisitId();
  write(KEYS.visit, fresh);
  return fresh;
}

export function loadForm(): FormState {
  const raw = read(KEYS.form);
  if (!raw) return EMPTY_FORM;
  try {
    return { ...EMPTY_FORM, ...(JSON.parse(raw) as Partial<FormState>) };
  } catch {
    return EMPTY_FORM;
  }
}

export function saveForm(form: FormState): void {
  write(KEYS.form, JSON.stringify(form));
}

export function loadResult(): Result | null {
  const raw = read(KEYS.result);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Result;
    return parsed && Array.isArray(parsed.slots) ? parsed : null;
  } catch {
    return null;
  }
}

export function saveResult(result: Result): void {
  write(KEYS.result, JSON.stringify(result));
}
