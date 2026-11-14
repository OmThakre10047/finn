"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost, apiDelete } from "@/lib/api";

type Settings = { volume_mult: number; price_move_pct: number; window_hours: number };
type WatchType = { key: string; label: string; is_enabled: number };

export default function SettingsPage() {
  const [s, setS] = useState<Settings | null>(null);
  const [wt, setWt] = useState<WatchType[]>([]);
  const [portfolio, setPortfolio] = useState<string[]>([]);
  const [newTicker, setNewTicker] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    apiGet<Settings>("/api/settings/alerts").then(setS).catch(() => {});
    apiGet<{ watch_types: WatchType[] }>("/api/settings/watch-types").then((d) => setWt(d.watch_types)).catch(() => {});
    apiGet<{ portfolio: { ticker: string }[] }>("/api/portfolio").then((d) => setPortfolio(d.portfolio.map((p) => p.ticker))).catch(() => {});
  }, []);

  async function save() {
    if (!s) return;
    await apiPost("/api/settings/alerts", s);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  }

  async function toggleWatch(k: string, v: boolean) {
    setWt((prev) => prev.map((w) => (w.key === k ? { ...w, is_enabled: v ? 1 : 0 } : w)));
    await apiPost("/api/settings/watch-types", { enabled: { [k]: v } });
  }

  async function addTicker() {
    const t = newTicker.trim().toUpperCase();
    if (!t) return;
    await apiPost("/api/portfolio", { ticker: t });
    setPortfolio((p) => (p.includes(t) ? p : [...p, t]));
    setNewTicker("");
  }

  async function removeTicker(t: string) {
    await apiDelete(`/api/portfolio/${t}`);
    setPortfolio((p) => p.filter((x) => x !== t));
  }

  return (
    <main className="mx-auto max-w-lg px-4 pt-6">
      <h1 className="mb-4 text-xl font-bold tracking-tight">Settings</h1>

      <div className="card mb-4 p-4">
        <h2 className="mb-3 text-sm font-bold">Alert thresholds</h2>
        {s && (
          <div className="space-y-3">
            <label className="block">
              <span className="num text-xs text-zinc-500">Volume alert: ≥ {s.volume_mult}× 20-day average</span>
              <input type="range" min={1} max={5} step={0.5} value={s.volume_mult}
                onChange={(e) => setS({ ...s, volume_mult: Number(e.target.value) })}
                className="mt-1 w-full accent-emerald-400" />
            </label>
            <label className="block">
              <span className="num text-xs text-zinc-500">Price move alert: |±| {s.price_move_pct}% in a day</span>
              <input type="range" min={1} max={15} step={0.5} value={s.price_move_pct}
                onChange={(e) => setS({ ...s, price_move_pct: Number(e.target.value) })}
                className="mt-1 w-full accent-emerald-400" />
            </label>
            <button className="btn-primary w-full" onClick={save}>
              {saved ? "Saved ✓" : "Save thresholds"}
            </button>
          </div>
        )}
      </div>

      <div className="card mb-4 p-4">
        <h2 className="mb-1 text-sm font-bold">Announcement types you care about</h2>
        <p className="mb-3 text-[11px] text-zinc-500">Watched types are pushed as alerts; the rest stay routine.</p>
        <div className="flex flex-wrap gap-1.5">
          {wt.map((w) => (
            <button
              key={w.key}
              onClick={() => toggleWatch(w.key, !w.is_enabled)}
              className={`chip ${w.is_enabled ? "chip-active" : ""}`}
            >
              {w.is_enabled ? "✓ " : ""}{w.label}
            </button>
          ))}
        </div>
      </div>

      <div className="card mb-4 p-4">
        <h2 className="mb-1 text-sm font-bold">Portfolio ({portfolio.length})</h2>
        <p className="mb-3 text-[11px] text-zinc-500">Digest + alerts cover these. Research works on any ticker regardless.</p>
        <div className="mb-3 flex flex-wrap gap-1.5">
          {portfolio.map((t) => (
            <span key={t} className="chip flex items-center gap-1">
              {t}
              <button className="text-zinc-400 hover:text-rose-400" onClick={() => removeTicker(t)}>×</button>
            </span>
          ))}
        </div>
        <div className="flex gap-2">
          <input className="input uppercase" placeholder="Add NSE ticker" value={newTicker}
            onChange={(e) => setNewTicker(e.target.value)} />
          <button className="btn-primary shrink-0" onClick={addTicker}>Add</button>
        </div>
      </div>
    </main>
  );
}
