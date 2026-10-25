import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";

const ROOT_ENV_MODULE = path.resolve(__dirname, "..", "root-env.mjs").replace(/\\/g, "/");
const NEXT_ENV_MODULE = path.resolve(__dirname, "..", "node_modules", "@next", "env", "dist", "index.js").replace(/\\/g, "/");

/**
 * Each case runs in a fresh Node process, like a real `next dev` / `next build`: Next first loads the
 * .env files of web/ (and caches that), then reads next.config.mjs, which loads the repo root's.
 */
function startLikeNext(opts: { fileEnv: string; realEnv?: Record<string, string>; useForceReload?: boolean }) {
  const root = mkdtempSync(path.join(os.tmpdir(), "autobrain-env-"));
  const web = path.join(root, "web");
  mkdirSync(web);
  writeFileSync(path.join(root, ".env"), opts.fileEnv);

  const script = `
    import { createRequire } from "node:module";
    const require = createRequire(import.meta.url);
    const nextEnv = require(${JSON.stringify(NEXT_ENV_MODULE)});
    const { loadRootEnv } = await import("file:///${ROOT_ENV_MODULE}");
    nextEnv.loadEnvConfig(${JSON.stringify(web)}, true);              // what Next does first
    ${opts.useForceReload === false
      ? `nextEnv.loadEnvConfig(${JSON.stringify(root)}, true);`        // the naive second call
      : `loadRootEnv(${JSON.stringify(root)}, true);`}                 // what next.config.mjs does
    console.log(JSON.stringify({
      ENGINE_SECRET: process.env.ENGINE_SECRET ?? null,
      ENGINE_URL: process.env.ENGINE_URL ?? null,
      FEEDBACK: process.env.NEXT_PUBLIC_FEEDBACK_FORM_URL ?? null,
    }));
  `;
  const clean = { ...process.env };
  for (const k of ["ENGINE_SECRET", "ENGINE_URL", "NEXT_PUBLIC_FEEDBACK_FORM_URL"]) delete clean[k];
  const done = spawnSync(process.execPath, ["--input-type=module", "-e", script], {
    env: { ...clean, ...(opts.realEnv ?? {}) },
    encoding: "utf-8",
  });
  expect(done.status, done.stderr).toBe(0);
  return JSON.parse(done.stdout.trim().split("\n").pop() as string) as Record<string, string | null>;
}

describe("the repo-root .env reaches the website", () => {
  const FILE = "ENGINE_SECRET=from-root-env\nENGINE_URL=http://localhost:8123\nNEXT_PUBLIC_FEEDBACK_FORM_URL=https://forms.example/x\n";

  it("is loaded by next.config.mjs's loadRootEnv", () => {
    expect(startLikeNext({ fileEnv: FILE })).toEqual({
      ENGINE_SECRET: "from-root-env",
      ENGINE_URL: "http://localhost:8123",
      FEEDBACK: "https://forms.example/x",
    });
  });

  it("would NOT be loaded by a plain second loadEnvConfig call (the bug forceReload fixes)", () => {
    expect(startLikeNext({ fileEnv: FILE, useForceReload: false }).ENGINE_SECRET).toBeNull();
  });

  it("a variable already set in the real environment wins over the file", () => {
    const seen = startLikeNext({ fileEnv: FILE, realEnv: { ENGINE_SECRET: "from-real-environment" } });
    expect(seen.ENGINE_SECRET).toBe("from-real-environment");
    expect(seen.ENGINE_URL).toBe("http://localhost:8123"); // the rest still comes from the file
  });
});
