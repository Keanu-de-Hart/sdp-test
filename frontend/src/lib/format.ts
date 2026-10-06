/** Number/date formatting helpers shared by tables, cards and tooltips. */

export function fmtInt(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "–";
  return Math.round(n).toLocaleString("en-US");
}

export function fmtSigned(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "–";
  const v = Math.round(n);
  return (v > 0 ? "+" : "") + v.toLocaleString("en-US");
}

export function fmtRate(n: number | null | undefined, digits = 3): string {
  if (n == null || !Number.isFinite(n)) return "–";
  return n.toFixed(digits);
}

export function fmtPct(n: number | null | undefined, digits = 1): string {
  if (n == null || !Number.isFinite(n)) return "–";
  return `${(n * 100).toFixed(digits)}%`;
}

export function fmtDate(ts: number | null | undefined): string {
  if (ts == null || !Number.isFinite(ts)) return "–";
  return new Date(ts * 1000).toISOString().slice(0, 10);
}

export function fmtDateTime(ts: number | null | undefined): string {
  if (ts == null || !Number.isFinite(ts)) return "–";
  const d = new Date(ts * 1000);
  return `${d.toISOString().slice(0, 10)} ${d.toISOString().slice(11, 16)} UTC`;
}

export function truncate(s: string, max = 60): string {
  return s.length > max ? s.slice(0, max - 1) + "…" : s;
}

/** Path made relative to a directory scope (the part below it). */
export function relPathName(path: string, scope: string): string {
  if (!path) return "/";
  const base = path.slice(scope ? scope.length + 1 : 0);
  return base || path;
}
