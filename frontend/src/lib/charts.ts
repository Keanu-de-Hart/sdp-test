/** Shared chart palette and helpers. */

export const C = {
  added: "#34d399",
  removed: "#f87171",
  growth: "#a78bfa",
  churn: "#60a5fa",
  grid: "rgba(148, 163, 184, 0.14)",
  axis: "#8ba3c0",
  text: "#9db0c9",
  tooltipBg: "#0f1a2e",
  tooltipBorder: "#223350",
  series: [
    "#60a5fa", "#34d399", "#a78bfa", "#fbbf24", "#f87171",
    "#22d3ee", "#fb923c", "#4ade80", "#f472b6", "#eab308",
    "#818cf8", "#2dd4bf",
  ],
} as const;

export const axisBase = {
  axisLine: { lineStyle: { color: "rgba(148, 163, 184, 0.3)" } },
  axisTick: { show: false },
  axisLabel: { color: C.text, fontSize: 11 },
  splitLine: { lineStyle: { color: C.grid } },
};

export const tooltipBase = {
  backgroundColor: C.tooltipBg,
  borderColor: C.tooltipBorder,
  borderWidth: 1,
  textStyle: { color: "#e6edf7", fontSize: 12 },
  extraCssText: "box-shadow: 0 8px 24px rgba(2,6,23,.5); border-radius: 8px;",
};

/** Diverging red → grey → green colour for a growth value. */
export function divergingColor(value: number, maxAbs: number): string {
  const mid = [82, 96, 128];
  const pos = [52, 211, 153];
  const neg = [248, 113, 113];
  if (!Number.isFinite(value) || maxAbs <= 0) return `rgb(${mid.join(",")})`;
  const t = Math.max(-1, Math.min(1, value / maxAbs));
  const target = t >= 0 ? pos : neg;
  const k = Math.pow(Math.abs(t), 0.65);
  const rgb = mid.map((m, i) => Math.round(m + (target[i] - m) * k));
  return `rgb(${rgb.join(",")})`;
}
