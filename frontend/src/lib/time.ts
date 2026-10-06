/** Calendar/time helpers. Everything metric-related is UTC (committer dates),
 *  so the UI works in UTC day boundaries for reproducibility. */
import type { Gran } from "../types";

export const DAY_S = 86400;

export function isGran(v: unknown): v is Gran {
  return v === "day" || v === "week" || v === "month";
}

/** 'YYYY-MM-DD' → UNIX seconds at UTC midnight, or null for empty/invalid. */
export function ymdToTs(ymd: string): number | null {
  if (!ymd) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(ymd);
  if (!m) return null;
  return Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])) / 1000;
}

/** UNIX seconds → 'YYYY-MM-DD' (UTC). */
export function tsToYmd(ts: number): string {
  return new Date(ts * 1000).toISOString().slice(0, 10);
}

/** Inclusive 'To' date → exclusive UNIX seconds (end of that UTC day). */
export function endOfDayTs(ymd: string): number | null {
  const ts = ymdToTs(ymd);
  return ts == null ? null : ts + DAY_S;
}

/** Exclusive end (UNIX seconds) of a timeseries bucket, used when a brush
 *  selection is translated back into a time-range filter. */
export function bucketEndTs(bucket: string, gran: Gran): number {
  const [y, mo, d] = bucket.split("-").map(Number);
  if (gran === "day") return Date.UTC(y, mo - 1, d) / 1000 + DAY_S;
  if (gran === "week") return Date.UTC(y, mo - 1, d) / 1000 + 7 * DAY_S;
  return Date.UTC(y, mo, 1) / 1000; // month: first day of the next month
}

export function nextGran(gran: Gran, dir: 1 | -1): Gran {
  const order: Gran[] = ["day", "week", "month"];
  const i = order.indexOf(gran) + dir;
  return order[Math.min(order.length - 1, Math.max(0, i))];
}
