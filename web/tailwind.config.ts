import type { Config } from "tailwindcss";

// Colours and fonts from docs/mockup_results_web.html
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0F1B24",
        brand: { DEFAULT: "#0B5F87", dark: "#08445F" },
        surface: "#F3F5F6",
        line: "#D5DDE2",
        chip: "#E2E8EC",
        muted: "#4B5A66",
        sky: { DEFAULT: "#E3F0F6", line: "#B8D7E6" },
        warn: { DEFAULT: "#B4460B", ink: "#8A3A0B", bg: "#FFF6EE", line: "#F1D3B8" },
        good: { DEFAULT: "#1F7A3A", ink: "#1F5F2E", bg: "#E6F2E8" },
      },
      fontFamily: {
        sans: ["Manrope", "Segoe UI", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
