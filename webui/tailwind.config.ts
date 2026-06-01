import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

/**
 * Tailwind config — wires our design tokens (defined as CSS vars in index.css)
 * into Tailwind utility classes. Keeps the source-of-truth in CSS variables so
 * runtime theme switching stays possible.
 */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Surfaces
        bg:          "hsl(var(--bg))",
        "bg-2":      "hsl(var(--bg-2))",
        panel:       "hsl(var(--panel))",
        "panel-2":   "hsl(var(--panel-2))",
        "panel-3":   "hsl(var(--panel-3))",
        border:      "hsl(var(--border))",
        "border-strong": "hsl(var(--border-strong))",

        // Text
        fg:          "hsl(var(--fg))",
        "fg-strong": "hsl(var(--fg-strong))",
        muted:       "hsl(var(--muted))",
        "muted-2":   "hsl(var(--muted-2))",

        // Brand
        primary:        "hsl(var(--primary))",
        "primary-strong": "hsl(var(--primary-strong))",
        "primary-soft": "hsl(var(--primary-soft))",
        accent2:        "hsl(var(--accent2))",

        // Semantic
        success:       "hsl(var(--success))",
        "success-soft": "hsl(var(--success-soft))",
        warning:       "hsl(var(--warning))",
        "warning-soft": "hsl(var(--warning-soft))",
        danger:        "hsl(var(--danger))",
        "danger-soft": "hsl(var(--danger-soft))",
        hot:           "hsl(var(--hot))",
        "hot-soft":    "hsl(var(--hot-soft))",
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "PingFang SC",
          "Microsoft YaHei",
          "system-ui",
          "sans-serif",
        ],
        mono: ["ui-monospace", "SF Mono", "Menlo", "monospace"],
      },
      fontSize: {
        xs:   ["11px", { lineHeight: "1.4" }],
        sm:   ["13px", { lineHeight: "1.45" }],
        base: ["14px", { lineHeight: "1.55" }],
        md:   ["15px", { lineHeight: "1.5" }],
        lg:   ["17px", { lineHeight: "1.45" }],
        xl:   ["20px", { lineHeight: "1.35" }],
        "2xl": ["26px", { lineHeight: "1.25" }],
        "3xl": ["32px", { lineHeight: "1.2" }],
      },
      borderRadius: {
        xs:   "var(--radius-xs)",
        sm:   "var(--radius-sm)",
        DEFAULT: "var(--radius-md)",
        md:   "var(--radius-md)",
        lg:   "var(--radius-lg)",
        xl:   "var(--radius-xl)",
        full: "9999px",
      },
      boxShadow: {
        card:     "var(--shadow-card)",
        elevated: "var(--shadow-elevated)",
        focus:    "var(--shadow-focus)",
      },
      transitionTimingFunction: {
        smooth: "cubic-bezier(0.4, 0, 0.2, 1)",
      },
      keyframes: {
        shimmer: {
          "0%":   { backgroundPosition: "100% 0" },
          "100%": { backgroundPosition: "-100% 0" },
        },
        flash: {
          "0%, 100%": { opacity: "1" },
          "50%":      { opacity: "0.5" },
        },
      },
      animation: {
        shimmer: "shimmer 1.6s linear infinite",
        flash:   "flash 1.5s ease-in-out",
      },
    },
  },
  plugins: [animate],
} satisfies Config;
