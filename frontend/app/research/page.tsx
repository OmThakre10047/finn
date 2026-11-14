"use client";

import { useState } from "react";
import { apiGet, apiPost, type ResearchReport } from "@/lib/api";

const DEMO = ["ETERNAL", "DMART", "KPITTECH", "CDSL", "VARUNBEV"];

const SECTION_ORDER = [
  "business_snapshot", "financial_snapshot", "trajectory", "balance_sheet",
  "cash_quality", "narrative_vs_numbers", "guidance", "bull_vs_bear",
];
const SECTION_LABEL: Record<string, string> = {
  business_snapshot: "Business snapshot", financial_snapshot: "Financial snapshot",
  trajectory: "Trajectory", balance_sheet: "Balance sheet", cash_quality: "Cash quality",
  narrative_vs_numbers: "Narrative vs numbers", guidance: "Guidance", bull_vs_bear: "Bull vs bear",
};

function PromiseTracker({ rows }: { rows: ResearchReport["promise_tracker"]["rows"] }) {
  if (!rows?.length) return null;
  const color = (v: string) =>
    v === "delivered" ? "text-accent" : v === "missed" ? "text-rose-400" : v === "partial" ? "text-amber-400" : "text-zinc-500";
  return (
    <div className="card mt-3 border-accent/40 p-3.5">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-bold">Promise Tracker</h3>
        <span className="text-[10px] text-zinc-500">promised vs delivered · last 4–5 quarters</span>
      </div>
      <div className="space-y-2.5">
        {rows.map((r, i) => (
          <div key={i} className="rounded-lg border border-zinc-200/70 p-2.5 dark:border-ink-700/70">
            <div className="flex items-center justify-between">
              <span className="num text-[11px] font-semibold">{r.period_promised}</span>
              <span className={`text-[10px] font-bold uppercase tracking-wide ${color(r.verdict)}`}>{r.verdict}</span>
            </div>
            <p className="mt-1 text-xs text-zinc-600 dark:text-zinc-300">
              <b>Promise:</b> {r.promise}
            </p>
            <p className="mt-0.5 text-xs text-zinc-600 dark:text-zinc-300">
              <b>Delivered:</b> {r.delivered}
            </p>
            {(r.citations?.length ?? 0) > 0 && (
              <div className="num mt-1.5 flex flex-wrap gap-1">
                {r.citations.map((c, j) => (
                  <span key={j} className="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] text-zinc-500 dark:bg-ink-800">
                    {c.doc} · {c.period}{c.page ? ` · p.${c.page}` : ""}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function ResearchPage() {
  const [ticker, setTicker] = useState("");
  const [report, setReport] = useState<ResearchReport | null>(null);
  const [status, setStatus] = useState<string>("");
  const [err, setErr] = useState<string | null>(null);

  async function load(t: string) {
    setErr(null);
    setReport(null);
    setStatus("Fetching primary sources…");
    try {
      let d = await apiPost<{ status: string; report?: ResearchReport }>(`/api/research/${t.toUpperCase()}`);
      let tries = 0;
      while (d.status === "pending" && tries < 60) {
        await new Promise((r) => setTimeout(r, 3000));
        setStatus(tries % 2 ? "Reading transcripts…" : "Extracting promises & numbers…");
        d = await apiGet(`/api/research/${t.toUpperCase()}`);
        tries++;
      }
      if (d.status === "done" && d.report) setReport(d.report);
      else if (d.status === "error") setErr(d.report ? "Report failed — check backend logs." : "Report failed.");
      else setStatus("Still working… try again shortly.");
    } catch (e) {
      setErr(String((e as Error).message));
    }
    setStatus("");
  }

  return (
    <main className="mx-auto max-w-lg px-4 pt-6">
      <h1 className="mb-1 text-xl font-bold tracking-tight">Research</h1>
      <p className="mb-4 text-[11px] text-zinc-500">Any NSE ticker · grounded only in annual reports + concall transcripts via screener.in.</p>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (ticker.trim()) load(ticker.trim());
        }}
      >
        <input
          className="input uppercase"
          placeholder="e.g. IRCTC"
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
        />
        <button className="btn-primary shrink-0" type="submit">
          Dig
        </button>
      </form>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {DEMO.map((t) => (
          <button key={t} className={`chip ${ticker.toUpperCase() === t ? "chip-active" : ""}`} onClick={() => { setTicker(t); load(t); }}>
            {t}
          </button>
        ))}
      </div>

      {status && <div className="card mt-4 animate-pulse p-4 text-sm text-zinc-500">{status}</div>}
      {err && <div className="card mt-4 p-4 text-sm text-rose-400">{err}</div>}

      {report && (
        <div className="mt-5">
          <div className="mb-1 flex items-baseline justify-between">
            <h2 className="text-lg font-bold">{report.name || report.ticker}</h2>
            <span className="num text-[10px] text-zinc-500">built {report.generated_at?.slice(0, 16).replace("T", " ")}</span>
          </div>
          <div className="mb-3 flex flex-wrap gap-1">
            {report.sources?.map((s, i) => (
              <a key={i} href={s.url} target="_blank" rel="noreferrer" className="chip">
                {s.kind} {s.period}
              </a>
            ))}
          </div>
          {SECTION_ORDER.filter((k) => report.sections?.[k]).map((k) => {
            const sec = report.sections[k];
            return (
              <div key={k} className="card mb-3 p-3.5">
                <h3 className="mb-2 text-sm font-bold">{SECTION_LABEL[k] || k}</h3>
                <div className="section-prose text-xs text-zinc-600 dark:text-zinc-300">
                  {sec.text.split("\n").map((line, i) =>
                    line.trim().startsWith("- ") || line.trim().startsWith("• ") ? (
                      <li key={i} className="ml-4 list-disc">{line.replace(/^[-•] /, "")}</li>
                    ) : line.trim() ? (
                      <p key={i}>{line}</p>
                    ) : null
                  )}
                </div>
                {(sec.citations?.length ?? 0) > 0 && (
                  <div className="num mt-2 flex flex-wrap gap-1">
                    {(sec.citations ?? []).slice(0, 6).map((c, j) => (
                      <span key={j} className="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] text-zinc-500 dark:bg-ink-800">
                        {c.doc} · {c.period}{c.page ? ` · p.${c.page}` : ""}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
          {report.promise_tracker && <PromiseTracker rows={report.promise_tracker.rows} />}
        </div>
      )}
    </main>
  );
}
