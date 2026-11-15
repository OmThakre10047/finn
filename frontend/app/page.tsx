"use client";

import { useEffect, useMemo, useState } from "react";
import { apiGet, relTime, CAT_LABEL, MUST_KNOW_CATS, type Announcement, type Digest } from "@/lib/api";
import { Sheet } from "@/components/ui";
import { RenderBody } from "@/components/Cards";
import { SnapshotBanner } from "@/components/WakeGate";

const WINDOWS = [
  { label: "24h", hours: 24 },
  { label: "3d", hours: 72 },
  { label: "7d", hours: 168 },
  { label: "30d", hours: 720 },
];

function DetailSheet({ a, onClose }: { a: Announcement | null; onClose: () => void }) {
  return (
    <Sheet open={!!a} onClose={onClose} title={a ? `${a.ticker} · ${CAT_LABEL[a.category] || a.category}` : ""}>
      {a && (
        <div>
          <h3 className="text-[15px] font-bold leading-snug">{a.headline}</h3>
          <div className="num mt-1 text-[11px] text-zinc-500">
            filed {relTime(a.published_at)} · priority {Math.round(a.priority)} · {a.materiality}
          </div>
          {a.subject && <p className="mt-3 text-[13px] leading-relaxed text-zinc-600 dark:text-zinc-300">{a.subject}</p>}
          <RenderBody a={a} />
          {a.pdf_url && (
            <a href={a.pdf_url} target="_blank" rel="noreferrer" className="btn-primary mt-4 inline-block">
              Open filing PDF ↗
            </a>
          )}
        </div>
      )}
    </Sheet>
  );
}

export default function TodayPage() {
  const [hours, setHours] = useState(24);
  const [custom, setCustom] = useState<number | null>(null);
  const [data, setData] = useState<Digest | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [detail, setDetail] = useState<Announcement | null>(null);
  const [routineOpen, setRoutineOpen] = useState(false);

  useEffect(() => {
    setData(null);
    apiGet<Digest>(`/api/digest?window_hours=${hours}`)
      .then(setData)
      .catch((e) => setErr(String(e.message || e)));
  }, [hours]);

  const [recent, setRecent] = useState<Digest | null>(null);
  useEffect(() => {
    if (data && data.stats.total === 0 && hours === 24) {
      apiGet<Digest>("/api/digest?window_hours=168")
        .then((d) => setRecent(d.stats.total > 0 ? d : null))
        .catch(() => setRecent(null));
    } else {
      setRecent(null);
    }
  }, [data, hours]);

  const { mustKnow, worthALook } = useMemo(() => {
    const mkAll = (data?.material || []).filter((a) => MUST_KNOW_CATS.has(a.category) || a.watched);
    const mk = mkAll.slice(0, 8);
    const wal = (data?.material || []).filter((a) => !mk.includes(a));
    return { mustKnow: mk, worthALook: wal };
  }, [data]);

  const quiet = data && data.stats.total === 0;

  return (
    <main className="mx-auto max-w-lg px-4 pt-5">
      <SnapshotBanner />
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h1 className="text-lg font-bold tracking-tight">
            FINN<span className="text-accent">.</span>
          </h1>
          <p className="text-[11px] text-zinc-500">Triage, not a feed.</p>
        </div>
        <div className="flex items-center gap-2">
          <ThemeButton />
        </div>
      </div>

      <div className="mb-3">
        {quiet ? (
          <>
            <h2 className="text-[22px] font-bold leading-tight">All quiet.</h2>
            <p className="mt-1 text-[13px] text-zinc-500">
              No filings across your 18 holdings in the last {hours < 24 ? `${hours}h` : `${Math.round(hours / 24)}d`}. Nothing needs you.
            </p>
          </>
        ) : (
          <>
            <h2 className="text-[22px] font-bold leading-tight">
              {mustKnow.length > 0 ? (
                <>
                  {mustKnow.length} {mustKnow.length === 1 ? "thing needs" : "things need"} your attention
                  {worthALook.length > 0 && <span className="text-zinc-400">, {worthALook.length} more to scan</span>}
                  <span className="text-accent">.</span>
                </>
              ) : (
                <>
                  Nothing must-know<span className="text-accent">.</span>
                  {worthALook.length > 0 && <span className="text-zinc-400"> {worthALook.length} worth a scan.</span>}
                </>
              )}
            </h2>
            <p className="num mt-1 text-[11px] text-zinc-500">
              {data?.stats.routine || 0} routine filings buried · last {hours < 24 ? `${hours}h` : `${Math.round(hours / 24)}d`}
            </p>
          </>
        )}
      </div>

      <div className="num mb-5 flex flex-wrap items-center gap-1.5">
        {WINDOWS.map((w) => (
          <button key={w.hours} onClick={() => setHours(w.hours)} className={`chip ${hours === w.hours ? "chip-active" : ""}`}>
            {w.label}
          </button>
        ))}
        {custom != null && (
          <button onClick={() => setCustom(null)} className={`chip ${![24, 72, 168, 720].includes(hours) ? "chip-active" : ""}`}>
            {hours}h ×
          </button>
        )}
        <button onClick={() => setCustom(custom === null ? 48 : null)} className="chip px-2">
          {custom === null ? "+ custom" : ""}
        </button>
        {custom !== null && (
          <input
            autoFocus
            type="number"
            min={1}
            max={720}
            placeholder="hrs"
            className="num w-16 rounded-full border border-accent/50 bg-transparent px-2 py-1 text-xs outline-none"
            onBlur={(e) => {
              const v = Number(e.target.value);
              if (v >= 1 && v <= 720) setHours(v);
              setCustom(null);
            }}
          />
        )}
      </div>

      {err && <div className="card p-4 text-sm text-rose-400">Backend unreachable: {err}</div>}
      {!data && !err && (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <div key={i} className="card h-16 animate-pulse" />
          ))}
        </div>
      )}

      {data && (
        <div className="space-y-5 pb-4">
          {mustKnow.length > 0 && (
            <section>
              <div className="eyebrow mb-2 flex items-center gap-2">
                Must know <span className="h-px flex-1 bg-zinc-200 dark:bg-ink-800" />
              </div>
              <div className="space-y-2">
                {mustKnow.map((a) => (
                  <button key={a.id} onClick={() => setDetail(a)} className="card w-full p-3.5 text-left active:opacity-90">
                    <div className="flex items-center justify-between">
                      <span className="text-[13px] font-bold">
                        {a.ticker}
                        <span className="ml-2 rounded bg-accent/15 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-accent">
                          {CAT_LABEL[a.category] || a.category}
                        </span>
                      </span>
                      <span className="num text-[10px] text-zinc-500">{relTime(a.published_at)}</span>
                    </div>
                    <div className="mt-1 text-[12px] leading-snug text-zinc-600 dark:text-zinc-300">{a.headline}</div>
                    <RenderBody a={a} />
                  </button>
                ))}
              </div>
            </section>
          )}

          {worthALook.length > 0 && (
            <section>
              <div className="eyebrow mb-2 flex items-center gap-2">
                Worth a look <span className="h-px flex-1 bg-zinc-200 dark:bg-ink-800" />
              </div>
              <div className="card divide-y divide-zinc-200/60 dark:divide-ink-800/80">
                {worthALook.map((a) => (
                  <button key={a.id} onClick={() => setDetail(a)} className="flex w-full items-center gap-3 px-3.5 py-2.5 text-left active:bg-zinc-50 dark:active:bg-ink-800">
                    <span className="num w-20 shrink-0 text-[12px] font-bold">{a.ticker}</span>
                    <span className="chip shrink-0 px-1.5 py-0.5 text-[9px]">{CAT_LABEL[a.category] || a.category}</span>
                    <span className="min-w-0 flex-1 truncate text-[12px] text-zinc-600 dark:text-zinc-300">{a.summary || a.headline}</span>
                    <span className="num shrink-0 text-[10px] text-zinc-500">{relTime(a.published_at)}</span>
                  </button>
                ))}
              </div>
            </section>
          )}

          {quiet && recent && recent.material.length > 0 && (
            <section>
              <div className="eyebrow mb-2 flex items-center gap-2">
                Last things that mattered <span className="h-px flex-1 bg-zinc-200 dark:bg-ink-800" />
              </div>
              <div className="space-y-2">
                {recent.material.slice(0, 3).map((a) => (
                  <button key={a.id} onClick={() => setDetail(a)} className="card w-full p-3.5 text-left active:opacity-90">
                    <div className="flex items-center justify-between">
                      <span className="text-[13px] font-bold">
                        {a.ticker}
                        <span className="ml-2 rounded bg-zinc-200 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-zinc-600 dark:bg-ink-800 dark:text-zinc-400">
                          {CAT_LABEL[a.category] || a.category}
                        </span>
                      </span>
                      <span className="num text-[10px] text-zinc-500">{relTime(a.published_at)}</span>
                    </div>
                    <div className="mt-1 text-[12px] leading-snug text-zinc-600 dark:text-zinc-300">{a.summary || a.headline}</div>
                  </button>
                ))}
              </div>
              <button onClick={() => setHours(168)} className="mt-2 w-full text-center text-[12px] font-semibold text-accent">
                See 7 days →
              </button>
            </section>
          )}

          {quiet && !recent && (
            <div className="card p-4">
              <p className="text-[13px] text-zinc-500">Widen the window to scan further back.</p>
            </div>
          )}

          {data.stats.routine > 0 && (
            <section>
              <button onClick={() => setRoutineOpen(!routineOpen)} className="card flex w-full items-center justify-between px-3.5 py-3 text-left">
                <span className="text-[12px]">
                  <span className="num font-bold">{data.stats.routine}</span>{" "}
                  <span className="text-zinc-500">routine filings — buried where they belong</span>
                </span>
                <span className="text-zinc-400">{routineOpen ? "−" : "+"}</span>
              </button>
              {routineOpen && (
                <div className="mt-2 space-y-1">
                  {data.routine_collapsed.items.map((a) => (
                    <button key={a.id} onClick={() => setDetail(a)} className="flex w-full items-center gap-3 px-3.5 py-2 text-left">
                      <span className="num w-20 shrink-0 text-[11px] font-semibold text-zinc-500">{a.ticker}</span>
                      <span className="min-w-0 flex-1 truncate text-[11px] text-zinc-500">{a.headline}</span>
                      <span className="num shrink-0 text-[10px] text-zinc-600">{relTime(a.published_at)}</span>
                    </button>
                  ))}
                </div>
              )}
            </section>
          )}
        </div>
      )}

      <DetailSheet a={detail} onClose={() => setDetail(null)} />
    </main>
  );
}

function ThemeButton() {
  const [dark, setDark] = useState(true);
  useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
  }, []);
  return (
    <button
      aria-label="Toggle theme"
      onClick={() => {
        const next = !dark;
        setDark(next);
        document.documentElement.classList.toggle("dark", next);
        try {
          localStorage.setItem("finn-theme", next ? "dark" : "light");
        } catch {}
      }}
      className="chip px-2.5"
    >
      {dark ? "☾" : "☀"}
    </button>
  );
}
