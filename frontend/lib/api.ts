export const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export async function apiGet<T>(path: string): Promise<T> {
  const r = await fetch(`${API}${path}`, { cache: "no-store" });
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
  payload: Record<string, unknown>;
  severity: string;
  created_at: string;
};

export type PromiseRow = {
  period_promised: string;
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
