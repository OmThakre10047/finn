export const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

let warm: Promise<boolean> | null = null;

export function wakeBackend(timeoutMs = 55000): Promise<boolean> {
  if (warm) return warm;
  warm = (async () => {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      try {
        const ctl = new AbortController();
        const t = setTimeout(() => ctl.abort(), 4000);
        const r = await fetch(`${API}/api/health`, { cache: "no-store", signal: ctl.signal });
        clearTimeout(t);
        if (r.ok) return true;
      } catch {}
      await new Promise((res) => setTimeout(res, 2500));
    }
    return false;
  })();
  return warm;
}

export async function apiGet<T>(path: string): Promise<T> {
  const r = await fetch(`${API}${path}`, { cache: "no-store" });
  if (r.status === 502 || r.status === 503 || r.status === 0) {
    const ok = await wakeBackend();
    if (!ok) throw new Error("backend asleep — try again in a minute");
    return apiGet<T>(path);
  }
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json();
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok && r.status !== 202) throw new Error(`${r.status} ${path}`);
  return r.json();
}

export async function apiDelete<T>(path: string): Promise<T> {
  const r = await fetch(`${API}${path}`, { method: "DELETE" });
  if (!r.ok) throw new Error(`${r.status} ${path}`);
  return r.json();
}

export function relTime(s: string | null): string {
  if (!s) return "";
  const d = new Date(s.replace(" ", "T") + (s.includes("Z") || s.includes("T") ? (s.includes("Z") ? "" : "Z") : ""));
  const t = isNaN(d.getTime()) ? null : d;
  if (!t) return s?.slice(0, 16) || "";
  const mins = Math.max(0, Math.floor((Date.now() - t.getTime()) / 60000));
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const h = Math.floor(mins / 60);
  if (h < 48) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export const CAT_LABEL: Record<string, string> = {
  results: "Results", mna: "M&A", fund_raise: "Fund raise", management_change: "Mgmt change",
  litigation: "Litigation", insider_trading: "Insider", earnings_call: "Concall", investor_meetings: "Investor meet",
  credit_rating: "Rating", dividend: "Dividend", bonus_split: "Bonus/Split", capex: "Capex",
  press_release: "Press release", postal_ballot: "Postal ballot", agm_egm: "AGM/EGM", pledging: "Pledging",
  unclassified: "Other",
};

export const MUST_KNOW_CATS = new Set(["results", "management_change", "mna", "litigation", "fund_raise", "pledging", "insider_trading"]);

export type Announcement = {
  id: number;
  ticker: string;
  headline: string;
  subject: string;
  category: string;
  materiality: string;
  priority: number;
  pdf_url: string | null;
  published_at: string;
  summary: string | null;
  watched: boolean;
  renders: Record<string, ResultsCard | BioCard | Record<string, unknown>>;
};

export type Digest = {
  window_hours: number;
  stats: { total: number; material: number; routine: number; rules_pct: number };
  routine_collapsed: { by_category: Record<string, number>; items: Announcement[] };
  material: Announcement[];
};

export type ResultsCard = {
  ticker: string;
  period: string;
  currency: string;
  rows: { label: string; current: number; qoq: number | null; yoy: number | null; page?: number }[];
  source: { doc: string; page: string };
  source_type?: "text" | "scanned";
  confidence: string;
};

export type BioCard = {
  person: string;
  role: string;
  bio: string;
  sources?: string[];
  source_type?: "filing" | "web" | "none";
};

export type Alert = {
  id: number;
  ticker: string;
  type: "material" | "volume" | "price";
  payload: Record<string, number | string>;
  severity: string;
  created_at: string;
};

export type Bars = {
  ticker: string;
  bars: { date: string; close: number; volume: number }[];
  avg20_volume: number | null;
};

export type Preview = {
  volume_fires: number;
  price_fires: number;
  total: number;
  examples: { ticker: string; type: string; date: string; ratio?: number; move_pct?: number }[];
};

export type PromiseRow = {
  period_promised: string;
  quarter_key?: string | null;
  promise: string;
  metric: string;
  target: string;
  delivered: string;
  verdict: "delivered" | "missed" | "partial" | "unverifiable";
  citations: { doc: string; period: string; page: string }[];
};

export type ResearchReport = {
  ticker: string;
  name: string;
  generated_at: string;
  sections: Record<string, { title: string; text: string; citations?: { doc: string; period: string; page: string }[] }>;
  promise_tracker: { rows: PromiseRow[] };
  sources: { kind: string; period: string; url: string }[];
};
