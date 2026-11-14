"use client";

import type { ResultsCard as ResultsCardT, BioCard as BioCardT } from "@/lib/api";

export function ResultsCardView({ data }: { data: ResultsCardT }) {
  return (
    <div className="mt-3 rounded-lg border border-accent/30 bg-accent/5 p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-accent">
          Results · {data.period}
        </span>
        <span className="text-[10px] text-zinc-500">
          {data.source?.doc ? `source: ${data.source.doc}${data.source.page ? ` p.${data.source.page}` : ""}` : ""}
        </span>
      </div>
      <table className="w-full text-left text-xs">
        <thead className="text-zinc-500">
          <tr>
            <th className="py-1 font-medium">₹ {data.currency || "Cr"}</th>
            <th className="py-1 text-right font-medium">This Q</th>
            <th className="py-1 text-right font-medium">QoQ</th>
            <th className="py-1 text-right font-medium">YoY</th>
          </tr>
        </thead>
        <tbody className="num">
          {data.rows?.map((r) => (
            <tr key={r.label} className="border-t border-zinc-200/60 dark:border-ink-700/60">
              <td className="py-1.5 font-medium">
                {r.label}
                {r.page ? <span className="ml-1 text-[9px] text-zinc-400">p.{r.page}</span> : null}
              </td>
              <td className="py-1.5 text-right">{r.current?.toLocaleString()}</td>
              <td className={`py-1.5 text-right ${(r.qoq ?? 0) >= 0 ? "text-accent" : "text-rose-400"}`}>
                {r.qoq == null ? "—" : `${r.qoq > 0 ? "+" : ""}${r.qoq}%`}
              </td>
              <td className={`py-1.5 text-right ${(r.yoy ?? 0) >= 0 ? "text-accent" : "text-rose-400"}`}>
                {r.yoy == null ? "—" : `${r.yoy > 0 ? "+" : ""}${r.yoy}%`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function BioCardView({ data }: { data: BioCardT }) {
  return (
    <div className="mt-3 rounded-lg border border-amber-400/30 bg-amber-400/5 p-3">
      <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-amber-400">
        Who&apos;s coming in
      </div>
      <div className="text-sm font-semibold">{data.person}</div>
      <div className="mb-1.5 text-xs text-zinc-500">{data.role}</div>
      <p className="text-xs leading-relaxed text-zinc-600 dark:text-zinc-300">{data.bio}</p>
      {data.sources && data.sources.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {data.sources.slice(0, 3).map((u, i) => (
            <a key={i} href={u} target="_blank" rel="noreferrer" className="chip text-[10px]">
              source {i + 1} ↗
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
