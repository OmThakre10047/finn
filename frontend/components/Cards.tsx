"use client";

import type { Announcement, ResultsCard, BioCard } from "@/lib/api";

export function ResultsTable({ card }: { card: ResultsCard }) {
  return (
    <div className="mt-2">
      <div className="num grid grid-cols-[1.4fr_1fr_0.9fr_0.9fr_0.5fr] gap-x-2 text-[11px] text-zinc-500">
        <span>₹ {card.currency || "Cr"}</span>
        <span className="text-right">This Q</span>
        <span className="text-right">QoQ</span>
        <span className="text-right">YoY</span>
        <span className="text-right">p.</span>
      </div>
      {card.rows?.map((r) => (
        <div key={r.label} className="num mt-1.5 grid grid-cols-[1.4fr_1fr_0.9fr_0.9fr_0.5fr] gap-x-2 text-[13px]">
          <span className="font-semibold">{r.label}</span>
          <span className="text-right">{r.current?.toLocaleString()}</span>
          <span className={`text-right ${(r.qoq ?? 0) >= 0 ? "text-accent" : "text-rose-400"}`}>
            {r.qoq == null ? "—" : `${r.qoq > 0 ? "+" : ""}${r.qoq}%`}
          </span>
          <span className={`text-right ${(r.yoy ?? 0) >= 0 ? "text-accent" : "text-rose-400"}`}>
            {r.yoy == null ? "—" : `${r.yoy > 0 ? "+" : ""}${r.yoy}%`}
          </span>
          <span className="text-right text-zinc-500">{r.page ?? "—"}</span>
        </div>
      ))}
      <div className="mt-2 text-[10px] text-zinc-500">
        {card.source_type === "scanned" ? `from scanned page ${card.source?.page || "?"}` : `results filing, page ${card.source?.page || "—"}`}
      </div>
    </div>
  );
}

export function RenderBody({ a }: { a: Announcement }) {
  const rc = a.renders?.results_card as ResultsCard | undefined;
  const bio = a.renders?.bio as BioCard | undefined;
  return (
    <div>
      {a.summary && <p className="text-[13px] leading-relaxed text-zinc-600 dark:text-zinc-300">{a.summary}</p>}
      {rc && rc.rows && (
        <div className="mt-3 rounded-lg border border-accent/25 bg-accent/5 p-3">
          <div className="text-[10px] font-bold uppercase tracking-[0.12em] text-accent">Results · {rc.period}</div>
          <ResultsTable card={rc} />
        </div>
      )}
      {bio && bio.bio && (
        <div className="mt-3 rounded-lg border border-amber-400/25 bg-amber-400/5 p-3">
          <div className="text-[10px] font-bold uppercase tracking-[0.12em] text-amber-400">Who&apos;s coming in</div>
          <div className="mt-1 text-sm font-semibold">{bio.person}</div>
          <div className="text-xs text-zinc-500">{bio.role}</div>
          <p className="mt-1.5 text-xs leading-relaxed text-zinc-600 dark:text-zinc-300">{bio.bio}</p>
          {bio.sources && bio.sources.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {bio.sources.slice(0, 3).map((u, i) => (
                <a key={i} href={u} target="_blank" rel="noreferrer" className="chip text-[10px]">
                  source {i + 1} ↗
                </a>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
