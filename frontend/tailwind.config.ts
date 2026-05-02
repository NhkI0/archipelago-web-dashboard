import type { Config } from "tailwindcss";

// Composio design tokens — see DESIGN-composio.md
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#0007cd",
          active: "#0005a3",
          glow: "#1a26ff",
        },
        ink: "#ffffff",
        body: "#a8a8a8",
        bodyStrong: "#ffffff",
        muted: "#888888",
        mutedSoft: "#666666",
        hairline: {
          DEFAULT: "#222222",
          soft: "#1a1a1a",
          strong: "#333333",
        },
        canvas: {
          DEFAULT: "#0f0f0f",
          deep: "#000000",
        },
        surface: {
          card: "#181818",
          cardElevated: "#222222",
          strong: "#2a2a2a",
        },
        accent: {
          cyan: "#00d4ff",
          violet: "#7b3aed",
        },
        semantic: {
          error: "#ff4d4d",
          success: "#33d17a",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "abcDiatype",
          "ui-sans-serif",
          "system-ui",
          "sans-serif",
        ],
        mono: ['"JetBrains Mono"', '"Fira Code"', "monospace"],
      },
      fontSize: {
        "display-mega": ["72px", { lineHeight: "1.05", letterSpacing: "-2.16px", fontWeight: "500" }],
        "display-xl":   ["56px", { lineHeight: "1.05", letterSpacing: "-1.68px", fontWeight: "500" }],
        "display-lg":   ["44px", { lineHeight: "1.10", letterSpacing: "-1.32px", fontWeight: "500" }],
        "display-md":   ["32px", { lineHeight: "1.15", letterSpacing: "-0.96px", fontWeight: "500" }],
        "display-sm":   ["24px", { lineHeight: "1.25", letterSpacing: "-0.5px",  fontWeight: "500" }],
        "title-md":     ["18px", { lineHeight: "1.40", fontWeight: "600" }],
        "title-sm":     ["16px", { lineHeight: "1.40", fontWeight: "600" }],
        "body-md":      ["16px", { lineHeight: "1.50", fontWeight: "400" }],
        "body-sm":      ["14px", { lineHeight: "1.50", fontWeight: "400" }],
        "caption":      ["13px", { lineHeight: "1.40", fontWeight: "400" }],
        "caption-up":   ["11px", { lineHeight: "1.40", letterSpacing: "0.88px", fontWeight: "600" }],
        "code":         ["13px", { lineHeight: "1.50", fontWeight: "400" }],
        "btn":          ["14px", { lineHeight: "1.00", fontWeight: "500" }],
      },
      borderRadius: {
        none: "0px",
        xs: "4px",
        sm: "6px",
        md: "8px",
        lg: "12px",
        xl: "16px",
        pill: "9999px",
      },
      spacing: {
        section: "96px",
      },
      boxShadow: {
        none: "none",
      },
    },
  },
  plugins: [],
} satisfies Config;
