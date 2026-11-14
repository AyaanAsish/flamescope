import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)",
        surface1: "var(--surface-1)",
        surface2: "var(--surface-2)",
        line: "var(--border)",
        "line-strong": "var(--border-strong)",
        fg: "var(--text)",
        muted: "var(--text-muted)",
        faint: "var(--text-faint)",
        accent: "var(--accent)",
        "accent-soft": "var(--accent-soft)",
        "accent-fg": "var(--accent-fg)",
        cool: "var(--cool)",
        success: "var(--success)",
        warning: "var(--warning)",
        danger: "var(--danger)",
        gas: "var(--gas)",
        liquid: "var(--liquid)",
        solid: "var(--solid)",
        "lens-habitat": "var(--lens-habitat)",
        "lens-modeling": "var(--lens-modeling)",
        "lens-controls": "var(--lens-controls)",
      },
      fontFamily: {
        sans: ["var(--font-inter)", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
      fontSize: {
        xs: ["12px", "1.5"],
        caption: ["13px", "1.5"],
        sm: ["14px", "1.5"],
        base: ["16px", "1.5"],
        xl: ["20px", "1.2"],
        "2xl": ["24px", "1.2"],
        "3xl": ["32px", "1.2"],
      },
      borderRadius: { card: "10px", control: "6px" },
      maxWidth: { content: "1440px" },
    },
  },
};

export default config;
