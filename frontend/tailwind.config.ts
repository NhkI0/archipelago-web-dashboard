import type { Config } from "tailwindcss";

// Notion design tokens — see DESIGN-notion.md.
// Class names are kept compatible with the previous Composio theme where
// possible (`bg-canvas`, `text-body`, `text-bodyStrong`, …) so existing JSX
// continues to type-check; values are remapped to the Notion palette.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#5645d4",
          active: "#4534b3",
          deep: "#3a2a99",
          glow: "#5645d4",
        },
        // Brand
        brand: {
          navy: "#0a1530",
          "navy-deep": "#070f24",
          "navy-mid": "#1a2a52",
          purple: "#7b3ff2",
          "purple-300": "#d6b6f6",
          "purple-800": "#391c57",
          pink: "#ff64c8",
          "pink-deep": "#a02e6d",
          orange: "#dd5b00",
          "orange-deep": "#793400",
          teal: "#2a9d99",
          green: "#1aae39",
          yellow: "#f5d75e",
          brown: "#523410",
          link: "#0075de",
        },
        // Pastel feature card tints
        card: {
          peach: "#ffe8d4",
          rose: "#fde0ec",
          mint: "#d9f3e1",
          lavender: "#e6e0f5",
          sky: "#dcecfa",
          yellow: "#fef7d6",
          "yellow-bold": "#f9e79f",
          cream: "#f8f5e8",
          gray: "#f0eeec",
        },

        // Page surfaces — light Notion canvas
        canvas: {
          DEFAULT: "#ffffff",
          deep: "#f6f5f4",          // formerly used as a darker card bg; now the soft surface
        },
        surface: {
          DEFAULT: "#f6f5f4",
          soft: "#fafaf9",
          card: "#ffffff",
          cardElevated: "#ffffff",
          strong: "#f6f5f4",
        },

        hairline: {
          DEFAULT: "#e5e3df",
          soft: "#ede9e4",
          strong: "#c8c4be",
        },

        // Text
        ink: "#1a1a1a",
        inkDeep: "#000000",
        bodyStrong: "#1a1a1a",     // primary copy
        body: "#5d5b54",           // slate
        muted: "#bbb8b1",
        mutedSoft: "#787671",      // steel
        charcoal: "#37352f",
        slate: "#5d5b54",
        steel: "#787671",
        stone: "#a4a097",
        onDark: "#ffffff",
        onDarkMuted: "#a4a097",

        semantic: {
          error: "#e03131",
          success: "#1aae39",
          warning: "#dd5b00",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "Notion Sans",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Helvetica",
          "sans-serif",
        ],
        mono: ['"JetBrains Mono"', '"Fira Code"', "monospace"],
      },
      fontSize: {
        // Notion type scale — keep keys backward-compatible.
        "display-mega": ["80px", { lineHeight: "1.05", letterSpacing: "-2px",   fontWeight: "600" }],
        "display-xl":   ["56px", { lineHeight: "1.10", letterSpacing: "-1px",   fontWeight: "600" }],
        "display-lg":   ["48px", { lineHeight: "1.15", letterSpacing: "-0.5px", fontWeight: "600" }],
        "display-md":   ["36px", { lineHeight: "1.20", letterSpacing: "-0.5px", fontWeight: "600" }],
        "display-sm":   ["28px", { lineHeight: "1.25",                          fontWeight: "600" }],
        "title-md":     ["22px", { lineHeight: "1.30", fontWeight: "600" }],
        "title-sm":     ["18px", { lineHeight: "1.40", fontWeight: "600" }],
        "subtitle":     ["18px", { lineHeight: "1.50", fontWeight: "400" }],
        "body-md":      ["16px", { lineHeight: "1.55", fontWeight: "400" }],
        "body-sm":      ["14px", { lineHeight: "1.50", fontWeight: "400" }],
        "caption":      ["13px", { lineHeight: "1.40", fontWeight: "400" }],
        "caption-up":   ["11px", { lineHeight: "1.40", letterSpacing: "1px",   fontWeight: "600" }],
        "code":         ["13px", { lineHeight: "1.50", fontWeight: "400" }],
        "btn":          ["14px", { lineHeight: "1.30", fontWeight: "500" }],
      },
      borderRadius: {
        none: "0px",
        xs: "4px",
        sm: "6px",
        md: "8px",
        lg: "12px",
        xl: "16px",
        "2xl": "20px",
        "3xl": "24px",
        pill: "9999px",
      },
      spacing: {
        section: "96px",
        "section-sm": "48px",
        hero: "120px",
      },
      boxShadow: {
        none: "none",
        soft: "rgba(15, 15, 15, 0.04) 0px 1px 2px 0px",
        card: "rgba(15, 15, 15, 0.08) 0px 4px 12px 0px",
        mockup: "rgba(15, 15, 15, 0.20) 0px 24px 48px -8px",
      },
    },
  },
  plugins: [],
} satisfies Config;
