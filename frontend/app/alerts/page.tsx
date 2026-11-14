"use client";

import { useEffect, useState } from "react";
import { apiGet, type Alert } from "@/lib/api";

function payloadLine(a: Alert): string {
  const p = (a.payload || {}) as Record<string, number | string>;
  if (a.type === "volume") return `Volume ${Number(p.volume)?.toLocaleString()} = ${p.ratio}× 20-day avg (${Number(p.avg20)?.toLocaleString()})`;
  if (a.type === "price") return `Moved ${Number(p.move_pct) > 0 ? "+" : ""}${p.move_pct}% to ₹${p.close} (prev ₹${p.prev_close})`;
  if (a.type === "material") return String(p.summary || p.headline || "Material announcement");
  return JSON.stringify(p);
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    apiGet<{ alerts: Alert[] }>("/api/alerts?since_hours=720")
      .then((d) => setAlerts(d.alerts))
      .catch((e) => setErr(String(e.message || e)));
  }, []);

  return (
    <main className="mx-auto max-w-lg px-4 pt-6">
      <h1 className="mb-1 text-xl font-bold tracking-tight">Alerts</h1>
      <p className="mb-4 text-[11px] text-zinc-500">Thresholds you set in Settings · volume & price checked every refresh.</p>
      {err && <div className="card p-4 text-sm text-rose-400">Backend unreachable: {err}</div>}
      {!alerts && !err && <div className="card animate-pulse p-4 text-sm text-zinc-500">Loading…</div>}
      {alerts && alerts.length === 0 && (
        <div className="card p-4 text-sm text-zinc-500">No threshold breaches yet. When a stock crosses your rules, it lands here.</div>
      )}
      <div className="space-y-2.5">
        {(alerts || []).map((a) => (
          <div key={a.id} className="card p-3.5">
            <div className="flex items-center justify-between">
              <span className="text-[13px] font-semibold">
                {a.ticker}{" "}
                <span className={`ml-1 rounded px-1.5 py-0.5 text-[10px] font-bold uppercase ${
                  a.type === "price" ? "bg-rose-400/15 text-rose-400" : a.type === "volume" ? "bg-amber-400/15 text-amber-400" : "bg-accent/15 text-accent"
                }`}>
                  {a.type === "price" ? "price move" : a.type}
                </span>
              </span>
              <span className="num text-[10px] text-zinc-500">{String(a.payload.date || a.created_at?.slice(0, 10) || "")}</span>
            </div>
            <p className="num mt-1 text-xs text-zinc-600 dark:text-zinc-300">{payloadLine(a)}</p>
          </div>
        ))}
      </div>
    </main>
  );
}
