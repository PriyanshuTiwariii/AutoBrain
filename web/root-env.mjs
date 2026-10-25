import nextEnv from "@next/env";

/**
 * Read the repo-root .env (ENGINE_URL, ENGINE_SECRET, NEXT_PUBLIC_FEEDBACK_FORM_URL) so the whole
 * project shares one .env file. Variables already set in the real environment win.
 *
 * Next.js has already loaded .env files for web/ and cached the result before it reads
 * next.config.mjs, so a plain second call returns that cache and loads nothing. forceReload makes it
 * read the repo root for real.
 */
export function loadRootEnv(rootDir, dev = process.env.NODE_ENV !== "production") {
  return nextEnv.loadEnvConfig(rootDir, dev, { info: () => {}, error: console.error }, true);
}
