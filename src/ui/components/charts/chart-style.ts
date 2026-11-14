export const chartTooltipStyle = {
  contentStyle: {
    background: "var(--surface-2)",
    border: "1px solid var(--border)",
    borderRadius: 6,
    color: "var(--text)",
    fontSize: 13,
  },
  labelStyle: { color: "var(--text-muted)" },
  itemStyle: { color: "var(--text)" },
  cursor: { stroke: "var(--border-strong)" },
} as const;

export const axisTick = { fill: "var(--text-faint)", fontSize: 12 } as const;
