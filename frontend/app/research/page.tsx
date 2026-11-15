"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { apiGet, apiPost, type ResearchReport, type PromiseRow } from "@/lib/api";
import { VerdictPill } from "@/components/ui";
import SectionErrorBoundary from "@/components/SectionErrorBoundary";

const DEMO = ["IRCTC", "ETERNAL", "DMART", "KPITTECH", "CDSL", "VARUNBEV"];

const SECTION_ORDER = [
  "business_snapshot", "financial_snapshot", "trajectory", "balance_sheet",
  "cash_quality", "narrative_vs_numbers", "guidance", "bull_vs_bear",
];
const SECTION_LABEL: Record<string, string> = {
  business_snapshot: "Business snapshot", financial_snapshot: "Financial snapshot",
  trajectory: "Trajectory", balance_sheet: "Balance sheet", cash_quality: "Cash quality",
  narrative_vs_numbers: "Narrative vs numbers", guidance: "Guidance", bull_vs_bear: "Bull vs bear",
};

function credibility(rows: PromiseRow[]) {
  const safe = (Array.isArray(rows) ? rows : []).filter((r) => r && typeof r === "object");
  const checkable = safe.filter((r) => String(r.verdict ?? "unverifiable") !== "unverifiable");
  const delivered = checkable.filter((r) => r.verdict === "delivered").length;
  const partial = checkable.filter((r) => r.verdict === "partial").length;
  const missed = checkable.filter((r) => r.verdict === "missed").length;
  const score = checkable.length ? Math.round((100 * (delivered + 0.5 * partial)) / checkable.length) : null;
  return { checkable: checkable.length, delivered, partial, missed, score, total: safe.length };
}

function firstPage(page: unknown): number | null {
  if (page == null) return null;
  const m = String(page).match(/\d+/);
  return m ? Number(m[0]) : null;
}

function asText(v: unknown): string {
  return String(v ?? "").trim();
}

function StructuredText({ text }: { text: unknown }) {
  if (text == null) return null;
  if (typeof text === "string") {
    return (
      <>
        {text.split("\n").map((line, j) =>
          line.trim().startsWith("- ") || line.trim().startsWith("• ") ? (
            <li key={j} className="ml-4 list-disc">{line.replace(/^[-•] /, "")}</li>
          ) : line.trim() ? (
            <p key={j}>{line}</p>
          ) : null
        )}
      </>
    );
  }
  if (Array.isArray(text)) {
    return (
      <div>
        {text.map((item, j) => {
          if (item == null) return null;
          if (typeof item === "object") {
            const o = item as Record<string, unknown>;
            const head = asText(o.promise || o.note || o.title || o.topic || o.metric);
            const detail = asText(o.target || o.delivered || o.value);
            const rest = Object.entries(o)
              .filter(([k]) => !["promise", "note", "title", "topic", "metric", "target", "delivered", "value", "citations", "page", "doc", "period", "quarter_key", "period_promised", "verdict"].includes(k))
              .map(([k, v]) => `${k}: ${asText(v)}`)
              .filter(Boolean);
            return (
              <div key={j} className="mb-1.5">
                {head && <span className="font-semibold">{head}</span>}
                {detail && <span> — {detail}</span>}
                {rest.length > 0 && <span className="block pl-3 text-[11px] text-zinc-500">{rest.join(" · ")}</span>}
              </div>
            );
          }
          return <p key={j}>• {String(item)}</p>;
        })}
      </div>
    );
  }
  if (typeof text === "object") {
    return (
      <div className="space-y-1">
        {Object.entries(text as Record<string, unknown>).map(([k, v]) => (
          <p key={k}>
            <span className="font-semibold">{k}: </span>
            {typeof v === "object" && v !== null ? JSON.stringify(v) : asText(v)}
          </p>
        ))}
      </div>
    );
  }
  return <p>{asText(text)}</p>;
}

function PromiseTrackerHero({ rows, sourceUrl }: { rows: PromiseRow[]; sourceUrl: (doc: string) => string | null }) {
  const safe = (Array.isArray(rows) ? rows : []).filter((r) => r && typeof r === "object");
  if (!safe.length) return null;
  const c = credibility(safe);
  return (
    <div className="card mt-4 border-accent/40 p-4">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-[15px] font-bold">Promise Tracker</h3>
          <p className="text-[11px] text-zinc-500">What management said vs what happened</p>
        </div>
        <div className="text-right">
          {c.score != null ? (
            <div className="num text-xl font-bold text-accent">{c.score}%</div>
          ) : (
            <div className="text-[11px] font-semibold text-zinc-500">Not enough checkable promises</div>
          )}
          {c.score != null && <div className="text-[9px] uppercase tracking-wide text-zinc-500">credibility</div>}
        </div>
      </div>
      <div className="num mt-1 text-[10px] text-zinc-500">
        {c.checkable} of {c.total} checkable · {c.delivered} delivered · {c.missed} missed
        {c.partial > 0 ? ` · ${c.partial} partial` : ""}
      </div>
      <div className="mt-3 space-y-2.5">
        {safe.map((r, i) => (
          <div key={i} className="rounded-lg border border-zinc-200/70 p-3 dark:border-ink-700/70">
            <div className="flex items-center justify-between">
              <span className="num text-[11px] font-semibold">{asText(r.period_promised) || "—"}</span>
              <VerdictPill v={asText(r.verdict) || "unverifiable"} />
            </div>
            <p className="mt-1.5 border-l-2 border-zinc-300 pl-2 text-[12px] italic leading-snug text-zinc-600 dark:border-ink-700 dark:text-zinc-300">
              “{asText(r.promise) || "—"}”
            </p>
            <div className="num mt-2 grid grid-cols-2 gap-2 text-[11px]">
              <div>
                <div className="text-[9px] uppercase tracking-wide text-zinc-500">target</div>
                <div>{asText(r.target) || "—"}</div>
              </div>
              <div>
                <div className="text-[9px] uppercase tracking-wide text-zinc-500">delivered</div>
                <div className={r.verdict === "missed" ? "text-rose-400" : r.verdict === "delivered" ? "text-accent" : ""}>
                  {asText(r.delivered) || "—"}
                </div>
              </div>
            </div>
            <div className="num mt-2 flex flex-wrap gap-1">
              {(Array.isArray(r.citations) ? r.citations : []).map((cit, j) => {
                if (!cit || typeof cit !== "object") return null;
                const url = sourceUrl(asText(cit.doc));
                const pg = firstPage(cit.page);
                const href = url ? `${url}#page=${pg ?? 1}` : null;
                const label = `${asText(cit.doc) || "doc"} · p.${cit.page ?? "?"}`;
                return href ? (
                  <a key={j} href={href} target="_blank" rel="noreferrer" className="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] text-zinc-500 underline decoration-zinc-400/40 dark:bg-ink-800">
                    {label} ↗
                  </a>
                ) : (
                  <span key={j} className="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] text-zinc-500 dark:bg-ink-800">
                    {label}
                  </span>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ResearchInner() {
  const searchParams = useSearchParams();
  const [ticker, setTicker] = useState("");
  const deepLink = searchParams.get("t");
  const [report, setReport] = useState<ResearchReport | null>(null);
  const [status, setStatus] = useState("");
  const [stage, setStage] = useState(0);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (deepLink && deepLink !== ticker) {
      setTicker(deepLink.toUpperCase());
      load(deepLink.toUpperCase());
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deepLink]);

  async function load(t: string) {
    setErr(null);
    setReport(null);
    setStatus("Starting…");
    setStage(0);
    try {
      let d = await apiPost<{ status: string; report?: ResearchReport; error?: string }>(`/api/research/${t.toUpperCase()}`);
      let tries = 0;
      while (d.status === "pending" && tries < 80) {
        await new Promise((r) => setTimeout(r, 3000));
        setStage(1 + (tries % 3));
        d = await apiGet<{ status: string; report?: ResearchReport; error?: string }>(`/api/research/${t.toUpperCase()}`);
        tries++;
      }
      if (d.status === "done" && d.report) setReport(d.report);
      else if (d.status === "error") setErr(d.error || "Report generation failed.");
      else setStatus("Still working — check back in a minute.");
    } catch (e) {
      setErr(String((e as Error).message));
    }
    setStatus("");
  }

  const sourceUrl = (doc: unknown) => {
    if (!report || !doc) return null;
    const norm = (s: unknown) => String(s ?? "").toLowerCase().replace(/\s+/g, " ").trim();
    const target = norm(doc);
    const hit = (report.sources || []).find((s) => norm(`${s.kind} ${s.period}`) === target || norm(s.period) === target);
    return hit?.url || null;
  };

  return (
    <main className="mx-auto max-w-lg px-4 pt-5 pb-4">
      <h1 className="text-lg font-bold tracking-tight">Research</h1>
      <p className="mb-4 text-[11px] text-zinc-500">Any NSE ticker · annual reports + concall transcripts only · zero news.</p>

      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (ticker.trim()) load(ticker.trim());
        }}
      >
        <input className="input num uppercase" placeholder="Any NSE symbol, e.g. IRCTC" value={ticker}
          onChange={(e) => setTicker(e.target.value)} />
        <button className="btn-primary shrink-0 px-5" type="submit">Dig</button>
      </form>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {DEMO.map((t) => (
          <button key={t} className={`chip ${ticker.toUpperCase() === t ? "chip-active" : ""}`} onClick={() => { setTicker(t); load(t); }}>
            {t}
          </button>
        ))}
      </div>

      {status && (
        <div className="card mt-4 p-4">
          <div className="text-[13px] font-semibold">{status}</div>
          <div className="num mt-2 space-y-1 text-[11px] text-zinc-500">
            <div className={stage >= 0 ? "text-accent" : ""}>{stage >= 0 ? "●" : "○"} resolving screener documents</div>
            <div className={stage >= 1 ? "text-accent" : ""}>{stage >= 1 ? "●" : "○"} downloading the annual report + last 4 concalls</div>
            <div className={stage >= 2 ? "text-accent" : ""}>{stage >= 2 ? "●" : "○"} extracting facts & promises, page by page</div>
            <div className={stage >= 3 ? "text-accent" : ""}>{stage >= 3 ? "●" : "○"} synthesising the dossier</div>
          </div>
          <p className="mt-2 text-[10px] text-zinc-500">This reads ~5 primary documents. Takes 2–3 minutes on free tiers.</p>
        </div>
      )}
      {err && (
        <div className="card mt-4 p-4">
          <div className="text-sm font-semibold text-rose-400">Research failed</div>
          <p className="num mt-1 break-words text-xs text-zinc-500">{err}</p>
          <button className="btn-primary mt-3" onClick={() => load(ticker.trim().toUpperCase())}>Retry</button>
        </div>
      )}

      {report && (
        <div className="mt-5">
          <div className="flex items-baseline justify-between">
            <h2 className="text-[17px] font-bold">{report.name || report.ticker}</h2>
            <span className="num text-[10px] text-zinc-500">{report.ticker}</span>
          </div>

          <SectionErrorBoundary label="Promise Tracker">
            <PromiseTrackerHero rows={report.promise_tracker?.rows || []} sourceUrl={sourceUrl} />
          </SectionErrorBoundary>

          <div className="mt-4 space-y-2">
            {SECTION_ORDER.filter((k) => report.sections?.[k]).map((k, i) => {
              const sec = report.sections[k] || {};
              return (
                <SectionErrorBoundary key={k} label={SECTION_LABEL[k] || k}>
                  <details className="card p-3.5" open={i < 1}>
                    <summary className="flex cursor-pointer list-none items-center justify-between">
                      <span className="text-[13px] font-bold">
                        <span className="num mr-2 text-zinc-500">{String(i + 1).padStart(2, "0")}</span>
                        {SECTION_LABEL[k] || k}
                      </span>
                      <span className="text-zinc-400 text-xs">{i < 1 ? "−" : "+"}</span>
                    </summary>
                    <div className="section-prose mt-2 text-[12px] text-zinc-600 dark:text-zinc-300">
                      <StructuredText text={sec.text} />
                    </div>
                    {(Array.isArray(sec.citations) ? sec.citations.length : 0) > 0 && (
                      <div className="num mt-2 flex flex-wrap gap-1">
                        {(sec.citations ?? []).slice(0, 5).map((c, j) => {
                          if (!c || typeof c !== "object") return null;
                          const url = sourceUrl(asText(c.doc));
                          const pg = firstPage(c.page);
                          const href = url ? `${url}#page=${pg ?? 1}` : null;
                          const label = `${asText(c.doc) || "doc"} · p.${c.page ?? "?"}`;
                          return href ? (
                            <a key={j} href={href} target="_blank" rel="noreferrer" className="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] text-zinc-500 underline decoration-zinc-400/40 dark:bg-ink-800">
                              {label} ↗
                            </a>
                          ) : (
                            <span key={j} className="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] text-zinc-500 dark:bg-ink-800">
                              {label}
                            </span>
                          );
                        })}
                      </div>
                    )}
                  </details>
                </SectionErrorBoundary>
              );
            })}
          </div>

          <div className="mt-4 rounded-lg border border-zinc-200 px-3 py-2.5 text-center dark:border-ink-700">
            <span className="num text-[11px] text-zinc-500">
              Built from {report.sources?.length || 0} primary documents · 0 news · ₹0
            </span>
            <div className="mt-1.5 flex flex-wrap justify-center gap-1">
              {report.sources?.map((s, i) => (
                <a key={i} href={s.url} target="_blank" rel="noreferrer" className="chip text-[9px]">
                  {s.kind} {s.period} ↗
                </a>
              ))}
            </div>
          </div>
        </div>
      )}

    </main>
  );
}

export default function ResearchPage() {
  return (<Suspense fallback={<main className="mx-auto max-w-lg px-4 pt-5" />}>
    <ResearchInner />
  </Suspense>);
}
