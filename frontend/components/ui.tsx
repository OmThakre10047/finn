"use client";

import { useEffect } from "react";

export function Sheet({ open, onClose, title, children }: { open: boolean; onClose: () => void; title?: string; children: React.ReactNode }) {
  useEffect(() => {
    if (open) {
      document.body.style.overflow = "hidden";
      return () => {
        document.body.style.overflow = "";
      };
    }
  }, [open]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[60]">
      <div className="sheet-backdrop absolute inset-0 bg-black/60" onClick={onClose} />
      <div className="sheet-panel absolute inset-x-0 bottom-0 max-h-[85%] overflow-y-auto rounded-t-2xl border-t border-zinc-300 bg-white pb-8 dark:border-ink-700 dark:bg-ink-900">
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-zinc-200 bg-white/95 px-4 py-3 backdrop-blur dark:border-ink-800 dark:bg-ink-900/95">
          <div className="mx-auto h-1 w-10 rounded-full bg-zinc-300 dark:bg-ink-700" style={{ position: "absolute", left: "50%", transform: "translateX(-50%)" }} />
          <span className="text-sm font-bold">{title}</span>
          <button onClick={onClose} className="text-lg leading-none text-zinc-400">×</button>
        </div>
        <div className="px-4 py-4">{children}</div>
      </div>
    </div>
  );
}

export function Sparkline({ closes, threshold, height = 36, stroke = "#34d399" }: { closes: number[]; threshold?: number | null; height?: number; stroke?: string }) {
  if (closes.length < 2) return <div style={{ height }} />;
  const w = 320;
  const min = Math.min(...closes, threshold ?? Infinity);
  const max = Math.max(...closes, threshold ?? -Infinity);
  const span = max - min || 1;
  const x = (i: number) => (i / (closes.length - 1)) * w;
  const y = (v: number) => height - 3 - ((v - min) / span) * (height - 6);
  const path = closes.map((c, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(c).toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${height}`} className="w-full" style={{ height }} preserveAspectRatio="none">
      {threshold != null && (
        <line x1="0" x2={w} y1={y(threshold)} y2={y(threshold)} stroke="#fb7185" strokeWidth="1" strokeDasharray="4 3" opacity="0.8" />
      )}
      <path d={path} fill="none" stroke={stroke} strokeWidth="1.6" />
      <circle cx={x(closes.length - 1)} cy={y(closes[closes.length - 1])} r="2.4" fill={stroke} />
    </svg>
  );
}

export function VolumeBars({ volumes, avg, height = 36 }: { volumes: number[]; avg?: number | null; height?: number }) {
  if (!volumes.length) return <div style={{ height }} />;
  const w = 320;
  const max = Math.max(...volumes, avg ?? 0);
  const bw = w / volumes.length - 2;
  return (
    <svg viewBox={`0 0 ${w} ${height}`} className="w-full" style={{ height }} preserveAspectRatio="none">
      {volumes.map((v, i) => {
        const h = (v / (max || 1)) * (height - 4);
        const breach = avg != null && v >= avg;
        return <rect key={i} x={i * (w / volumes.length) + 1} y={height - h} width={bw} height={h} fill={breach ? "#fb7185" : "#3f3f46"} />;
      })}
      {avg != null && (
        <line x1="0" x2={w} y1={height - (avg / (max || 1)) * (height - 4)} y2={height - (avg / (max || 1)) * (height - 4)} stroke="#34d399" strokeWidth="1" strokeDasharray="4 3" />
      )}
    </svg>
  );
}

const VERDICT_STYLES: Record<string, string> = {
  delivered: "bg-accent/15 text-accent",
  missed: "bg-rose-400/15 text-rose-400",
  partial: "bg-amber-400/15 text-amber-400",
  unverifiable: "bg-zinc-200 text-zinc-500 dark:bg-ink-800 dark:text-zinc-400",
};

export function VerdictPill({ v }: { v: string }) {
  return (
    <span className={`rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide ${VERDICT_STYLES[v] || VERDICT_STYLES.unverifiable}`}>
      {v}
    </span>
  );
}

export function Stat({ value, label, tone = "" }: { value: string | number; label: string; tone?: string }) {
  return (
    <div>
      <div className={`num text-2xl font-bold leading-none ${tone}`}>{value}</div>
      <div className="mt-1 text-[10px] uppercase tracking-[0.12em] text-zinc-500">{label}</div>
    </div>
  );
}
