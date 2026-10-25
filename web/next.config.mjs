import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadRootEnv } from "./root-env.mjs";

// One .env for the whole project. Values are only exposed to the browser if they start with NEXT_PUBLIC_.
loadRootEnv(path.resolve(path.dirname(fileURLToPath(import.meta.url)), ".."));

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  eslint: { ignoreDuringBuilds: true },
};

export default nextConfig;
