"use client";

import { useEffect, useState } from "react";
import { apiGet, type Digest, type Announcement, type ResultsCard as ResultsCardData, type BioCard as BioCardData } from "@/lib/api";
import { ResultsCardView, BioCardView } from "@/components/Cards";

const WINDOWS = [
  { label: "24h", hours: 24 },
  { label: "48h", hours: 48 },
  { label: "3d", hours: 72 },
  { label: "7d", hours: 168 },
  { label: "30d", hours: 720 },
];

function relTime(s: string | null): string {
  if (!s) return "";
  const d = new Date(s.replace(" ", "T") + (s.includes("Z") ? "" : "Z"));
  if (isNaN(d.getTime())) return s;
  const mins = Math.max(0, Math.floor((Date.now() - d.getTime()) / 60000));
  if (mins < 60) return `${mins}m ago`;
  const h = Math.floor(mins / 60);
  if (h < 48) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

const CAT_LABEL: Record<string, string> = {
  results: "Results", mna: "M&A", fund_raise: "Fund raise", management_change: "Mgmt change",
  litigation: "Litigation", insider_trading: "Insider", earnings_call: "Concall", investor_meetings: "Investor meet",
  credit_rating: "Rating", dividend: "Dividend", bonus_split: "Bonus/Split", capex: "Capex",
  press_release: "Press release", postal_ballot: "Postal ballot", agm_egm: "AGM/EGM", pledging: "Pledging",
  unclassified: "Other",
};

function MaterialCard({ a }: { a: Announcement }) {
  const [open, setOpen] = useState(true);
  const watched = a.watched;
  return (
    <div className="card p-3.5">
      <button className="flex w-full items-start gap-2 text-left" onClick={() => setOpen(!open)}>
        <span
          className={`mt-0.5 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide ${
            watched ? "bg-accent/15 text-accent" : "bg-zinc-200 text-zinc-600 dark:bg-ink-800 dark:text-zinc-400"
          }`}
        >
          {CAT_LABEL[a.category] || a.category}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[13px] font-semibold leading-snug">
            {a.ticker} <span className="font-normal text-zinc-600 dark:text-zinc-400">· {a.headline}</span>
          </span>
          <span className="num mt-0.5 block text-[11px] text-zinc-500">
            {relTime(a.published_at)} · priority {Math.round(a.priority)}
          </span>
        </span>
        <span className="text-zinc-400">{open ? "−" : "+"}</span>
      </button>
      {open && (
        <div className="mt-2 space-y-2">
          {a.summary && <p className="text-xs leading-relaxed text-zinc-600 dark:text-zinc-300">{a.summary}</p>}
          {a.renders?.results_card && <ResultsCardView data={a.renders.results_card as ResultsCardData} />}
          {a.renders?.bio && <BioCardView data={a.renders.bio as BioCardData} />}
          {a.pdf_url && (
            <a href={a.pdf_url} target="_blank" rel="noreferrer" className="inline-block text-[11px] text-accent underline">
              filing PDF ↗
            </a>
          )}
        </div>
      )}
    </div>
  );
}

export default function DigestPage() {
  const [hours, setHours] = useState(24);
  const [data, setData] = useState<Digest | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [routineOpen, setRoutineOpen] = useState(false);

  useEffect(() => {
    setData(null);
    apiGet<Digest>(`/api/digest?window_hours=${hours}`)
      .then(setData)
      .catch((e) => setErr(String(e.message || e)));
  }, [hours]);

  return (
    <main className="mx-auto max-w-lg px-4 pt-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight">
            FINN<span className="text-accent">.</span>
          </h1>
          <p className="text-[11px] text-zinc-500">Your portfolio, only what matters.</p>
        </div>
        <button
          className="chip"
          onClick={async () => {
            await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000"}/api/refresh`, { method: "POST" });
            setHours((h) => h);
            apiGet<Digest>(`/api/digest?window_hours=${hours}`).then(setData).catch(() => {});
          }}
        >
          ↻ Refresh
        </button>
      </div>

      <div className="num mb-3 flex gap-2 overflow-x-auto pb-1">
        {WINDOWS.map((w) => (
          <button
            key={w.hours}
            onClick={() => setHours(w.hours)}
            className={`chip ${hours === w.hours ? "chip-active" : ""}`}
          >
            {w.label}
          </button>
        ))}
      </div>

      {err && <div className="card p-4 text-sm text-rose-400">Backend unreachable: {err}</div>}
      {!data && !err && <div className="card animate-pulse p-4 text-sm text-zinc-500">Loading digest…</div>}

      {data && (
        <>
          <div className="num mb-4 grid grid-cols-3 gap-2 text-center">
            <div className="card p-2.5">
              <div className="text-lg font-bold text-accent">{data.stats.material}</div>
              <div className="text-[10px] uppercase tracking-wide text-zinc-500">material</div>
            </div>
            <div className="card p-2.5">
              <div className="text-lg font-bold">{data.stats.routine}</div>
              <div className="text-[10px] uppercase tracking-wide text-zinc-500">routine · collapsed</div>
            </div>
            <div className="card p-2.5">
              <div className="text-lg font-bold">{data.stats.rules_pct}%</div>
              <div className="text-[10px] uppercase tracking-wide text-zinc-500">free · rules</div>
            </div>
          </div>

          <div className="space-y-3">
            {data.material.length === 0 && (
              <div className="card p-4 text-sm text-zinc-500">
                No material announcements in this window. Quiet is good.
              </div>
            )}
            {data.material.map((a) => (
              <MaterialCard key={a.id} a={a} />
            ))}
          </div>

          <button
            onClick={() => setRoutineOpen(!routineOpen)}
            className="card mt-4 flex w-full items-center justify-between p-3 text-left text-xs"
          >
            <span>
              <span className="font-semibold">Routine filings</span>{" "}
              <span className="text-zinc-500">
                ({Object.entries(data.routine_collapsed.by_category).map(([k, v]) => `${CAT_LABEL[k] || k} ×${v}`).join(", ") || "none"})
              </span>
            </span>
            <span className="text-zinc-400">{routineOpen ? "−" : "+"}</span>
          </button>
          {routineOpen && (
            <div className="mt-2 space-y-1.5">
              {data.routine_collapsed.items.map((a) => (
                <div key={a.id} className="card flex items-center justify-between px-3 py-2 text-[11px]">
                  <span className="min-w-0 truncate text-zinc-600 dark:text-zinc-400">
                    <b className="text-zinc-800 dark:text-zinc-200">{a.ticker}</b> · {a.headline}
                  </span>
                  <span className="num ml-2 shrink-0 text-zinc-500">{relTime(a.published_at)}</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </main>
  );
}
