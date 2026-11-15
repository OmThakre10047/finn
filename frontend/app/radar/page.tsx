"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { apiGet, apiPost, relTime, CAT_LABEL, type Alert, type Bars, type Preview } from "@/lib/api";
import { Sparkline, VolumeBars, Sheet } from "@/components/ui";
import { AlertSheetBody } from "@/components/AlertSheetBody";

function AlertCard({ a, onOpen }: { a: Alert; onOpen: () => void }) {
  const [bars, setBars] = useState<Bars | null>(null);
  useEffect(() => {
    apiGet<Bars>(`/api/bars/${a.ticker}?days=30`).then(setBars).catch(() => {});
  }, [a.ticker]);

  const closes = (bars?.bars || []).map((b) => b.close);
  const vols = (bars?.bars || []).map((b) => b.volume);
  const avg = bars?.avg20_volume ?? null;

  return (
    <button onClick={onOpen} className="card w-full p-3.5 text-left active:opacity-90">
      <div className="flex items-center justify-between">
        <span className="text-[13px] font-bold">
          {a.ticker}
          <span className={`ml-2 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide ${
            a.type === "price" ? "bg-rose-400/15 text-rose-400" : a.type === "volume" ? "bg-amber-400/15 text-amber-400" : "bg-accent/15 text-accent"
          }`}>
            {a.type === "price" ? "price move" : a.type}
          </span>
        </span>
        <span className="num text-[10px] text-zinc-500">{a.payload.date || relTime(a.created_at)}</span>
      </div>
      <p className="num mt-1 text-[12px] text-zinc-600 dark:text-zinc-300">
        {a.type === "volume" && <>Volume {Number(a.payload.volume)?.toLocaleString()} = {a.payload.ratio}× 20-day avg</>}
        {a.type === "price" && <>{Number(a.payload.move_pct) > 0 ? "+" : ""}{a.payload.move_pct}% → ₹{a.payload.close}</>}
      </p>
      <div className="mt-2">
        {a.type === "price" && closes.length > 2 && (
          <>
            <Sparkline closes={closes} threshold={Number(a.payload.prev_close)} stroke="#34d399" />
            <div className="num mt-0.5 flex justify-between text-[9px] text-zinc-500">
              <span>{bars?.bars[0]?.date?.slice(5)}</span>
              <span className="text-rose-400/80">— threshold ₹{a.payload.prev_close} ±{Math.abs(Number(a.payload.move_pct))}% —</span>
              <span>now</span>
            </div>
          </>
        )}
        {a.type === "volume" && vols.length > 2 && (
          <>
            <VolumeBars volumes={vols.slice(-20)} avg={avg} />
            <div className="num mt-0.5 flex justify-between text-[9px] text-zinc-500">
              <span>last 20 sessions</span>
              <span className="text-accent/80">— 20-day avg {avg?.toLocaleString()} —</span>
              <span>now</span>
            </div>
          </>
        )}
      </div>
    </button>
  );
}

export default function RadarPage() {
  const [alerts, setAlerts] = useState<Alert[] | null>(null);
  const [mult, setMult] = useState<number>(2.0);
  const [pct, setPct] = useState<number>(4.0);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [watch, setWatch] = useState<Record<string, boolean>>({});
  const [detail, setDetail] = useState<Alert | null>(null);
  const [saving, setSaving] = useState("");
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    apiGet<{ alerts: Alert[] }>("/api/alerts?since_hours=720").then((d) => setAlerts(d.alerts)).catch(() => {});
    apiGet<{ volume_mult: number; price_move_pct: number }>("/api/settings/alerts").then((s) => {
      setMult(s.volume_mult);
      setPct(s.price_move_pct);
    }).catch(() => {});
    apiGet<{ watch_types: { key: string; label: string; is_enabled: number }[] }>("/api/settings/watch-types")
      .then((d) => setWatch(Object.fromEntries(d.watch_types.map((w) => [w.key, !!w.is_enabled]))))
      .catch(() => {});
  }, []);

  const runPreview = useCallback((vm: number, pp: number) => {
    if (debounce.current) clearTimeout(debounce.current);
    debounce.current = setTimeout(() => {
      apiGet<Preview>(`/api/alerts/preview?volume_mult=${vm}&price_move_pct=${pp}`).then(setPreview).catch(() => {});
    }, 350);
  }, []);

  useEffect(() => {
    runPreview(mult, pct);
  }, [mult, pct, runPreview]);

  async function save() {
    setSaving("…");
    await apiPost("/api/settings/alerts", { volume_mult: mult, price_move_pct: pct });
    setSaving("saved ✓");
    setTimeout(() => setSaving(""), 1500);
  }

  const materialAlerts = (alerts || []).filter((a) => a.type === "material");

  return (
    <main className="mx-auto max-w-lg px-4 pt-5 pb-4">
      <h1 className="text-lg font-bold tracking-tight">Radar</h1>
      <p className="mb-4 text-[11px] text-zinc-500">You decide what “unusual” means. FINN watches every close.</p>

      <section className="card mb-5 p-3.5">
        <div className="eyebrow mb-3">Rules editor</div>
        <label className="block">
          <div className="num mb-1 flex justify-between text-[12px]">
            <span>Volume ≥ <b>{mult.toFixed(1)}×</b> 20-day avg</span>
          </div>
          <input type="range" min={0.5} max={5} step={0.1} value={mult}
            onChange={(e) => setMult(Number(e.target.value))}
            className="w-full accent-emerald-400" />
        </label>
        <label className="mt-3 block">
          <div className="num mb-1 text-[12px]">Price move ≥ |±{pct.toFixed(1)}%| in a day</div>
          <input type="range" min={1} max={15} step={0.5} value={pct}
            onChange={(e) => setPct(Number(e.target.value))}
            className="w-full accent-emerald-400" />
        </label>

        {preview && (
          <div className="mt-3 rounded-lg border border-zinc-200/70 bg-zinc-50 p-2.5 dark:border-ink-700/70 dark:bg-ink-800">
            <div className="num text-[12px]">
              Would have fired <b className="text-accent">{preview.total}</b> times in the last 30 days
              <span className="text-zinc-500"> ({preview.volume_fires} volume · {preview.price_fires} price)</span>
            </div>
            {preview.examples.length > 0 && (
              <div className="num mt-1 space-y-0.5 text-[10px] text-zinc-500">
                {preview.examples.slice(0, 3).map((e, i) => (
                  <div key={i}>
                    {e.date?.slice(5)} {e.ticker} {e.type === "volume" ? `${e.ratio}× avg` : `${e.move_pct}%`}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="mt-3">
          <div className="eyebrow mb-2">Announcement types you care about</div>
          <div className="flex flex-wrap gap-1.5">
            {Object.entries(watch).map(([k, v]) => (
              <button
                key={k}
                className={`chip ${v ? "chip-active" : ""}`}
                onClick={async () => {
                  setWatch({ ...watch, [k]: !v });
                  await apiPost("/api/settings/watch-types", { enabled: { [k]: !v } });
                }}
              >
                {v ? "✓ " : ""}{CAT_LABEL[k] || k}
              </button>
            ))}
          </div>
        </div>

        <button className="btn-primary mt-3 w-full" onClick={save}>
          {saving || "Save rules"}
        </button>
      </section>

      <section>
        <div className="eyebrow mb-2 flex items-center gap-2">
          Fired <span className="h-px flex-1 bg-zinc-200 dark:bg-ink-800" />
        </div>
        {!alerts && <div className="card h-16 animate-pulse" />}
        {alerts && alerts.length === 0 && (
          <div className="card p-4 text-[13px] text-zinc-500">
            Nothing has crossed your thresholds yet. The preview above shows how sensitive your current rules are.
          </div>
        )}
        <div className="space-y-2.5">
          {materialAlerts.map((a) => (
            <button key={a.id} onClick={() => setDetail(a)} className="card w-full p-3.5 text-left">
              <div className="flex items-center justify-between">
                <span className="text-[13px] font-bold">
                  {a.ticker}
                  <span className="ml-2 rounded bg-accent/15 px-1.5 py-0.5 text-[10px] font-bold uppercase text-accent">
                    {String(a.payload.category ? CAT_LABEL[String(a.payload.category)] || a.payload.category : "material")}
                  </span>
                </span>
                <span className="num text-[10px] text-zinc-500">{relTime(a.created_at)}</span>
              </div>
              <p className="mt-1 text-[12px] text-zinc-600 dark:text-zinc-300">{String(a.payload.summary || a.payload.headline || "")}</p>
            </button>
          ))}
          {(alerts || []).filter((a) => a.type !== "material").map((a) => (
            <AlertCard key={a.id} a={a} onOpen={() => setDetail(a)} />
          ))}
        </div>
      </section>

      <Sheet open={!!detail} onClose={() => setDetail(null)} title={detail ? `${detail.ticker} · ${detail.type === "price" ? "price move" : detail.type}` : ""}>
        {detail && <AlertSheetBody a={detail} />}
      </Sheet>
    </main>
  );
}
