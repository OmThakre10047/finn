"use client";

import { useEffect, useState } from "react";
import { apiGet, type Alert, type Bars } from "@/lib/api";
import { Sparkline, VolumeBars } from "@/components/ui";

function sentence(a: Alert): string {
  const d = a.payload.date || "";
  const day = typeof d === "string" && d.length >= 10 ? d.slice(5).replace("-", "/") : "";
  if (a.type === "price") {
    const move = Number(a.payload.move_pct);
    return `${a.ticker} closed ${move > 0 ? "+" : ""}${move}% at ₹${a.payload.close} on ${day}, beyond your ±${Math.abs(move)}% rule.`;
  }
  if (a.type === "volume") {
    return `${a.ticker} traded ${Number(a.payload.volume)?.toLocaleString()} shares on ${day} — ${a.payload.ratio}× its 20-day average (${Number(a.payload.avg20)?.toLocaleString()}).`;
  }
  const cat = String(a.payload.category || "").replace("_", " ");
  return `${a.ticker} filed ${cat}: "${a.payload.headline || a.payload.summary || ""}" — a type you watch.`;
}

export function AlertSheetBody({ a }: { a: Alert }) {
  const [bars, setBars] = useState<Bars | null>(null);
  const [rules, setRules] = useState<{ volume_mult: number; price_move_pct: number } | null>(null);
  useEffect(() => {
    apiGet<Bars>(`/api/bars/${a.ticker}?days=30`).then(setBars).catch(() => {});
    apiGet<{ volume_mult: number; price_move_pct: number }>("/api/settings/alerts").then(setRules).catch(() => {});
  }, [a.ticker]);
  const closes = (bars?.bars || []).map((b) => b.close);
  const vols = (bars?.bars || []).map((b) => b.volume);
  const avg = bars?.avg20_volume ?? null;
  const text =
    a.type === "price"
      ? `${a.ticker} closed ${Number(a.payload.move_pct) > 0 ? "+" : ""}${a.payload.move_pct}% at ₹${a.payload.close} on ${String(a.payload.date || "").slice(5).replace("-", "/")}, beyond your ±${rules?.price_move_pct ?? Math.abs(Number(a.payload.move_pct))}% rule.`
      : a.type === "volume"
        ? `${a.ticker} traded ${Number(a.payload.volume)?.toLocaleString()} shares on ${String(a.payload.date || "").slice(5).replace("-", "/")} — ${a.payload.ratio}× its 20-day average (${Number(a.payload.avg20)?.toLocaleString()}); your rule is ${rules?.volume_mult ?? "2.0"}×.`
        : sentence(a);

  return (
    <div>
      <p className="num text-[13px] leading-relaxed">{text}</p>
      <div className="mt-3 rounded-lg border border-zinc-200/70 p-3 dark:border-ink-700/70">
        {a.type === "price" && closes.length > 2 && (
          <>
            <Sparkline closes={closes} threshold={Number(a.payload.prev_close)} />
            <div className="num mt-0.5 flex justify-between text-[9px] text-zinc-500">
              <span>{bars?.bars[0]?.date?.slice(5)}</span>
              <span className="text-rose-400/80">— your ±{Math.abs(Number(a.payload.move_pct))}% line —</span>
              <span>now</span>
            </div>
          </>
        )}
        {a.type === "volume" && vols.length > 2 && (
          <>
            <VolumeBars volumes={vols.slice(-20)} avg={avg} />
            <div className="num mt-0.5 flex justify-between text-[9px] text-zinc-500">
              <span>last 20 sessions</span>
              <span className="text-accent/80">— 20-day avg —</span>
              <span>now</span>
            </div>
          </>
        )}
        {a.type === "material" && (
          <p className="text-[12px] text-zinc-500">End-of-day data chart not applicable for announcement alerts.</p>
        )}
      </div>
      <div className="num mt-2 text-[10px] text-zinc-500">
        fired {a.created_at?.slice(0, 16).replace("T", " ")} · severity {a.severity}
      </div>
      <a href={`/research?t=${a.ticker}`} className="btn-primary mt-4 inline-block">
        Research {a.ticker} →
      </a>
    </div>
  );
}
