"use client";

import { useEffect, useState } from "react";
import { API, wakeBackend } from "@/lib/api";

export function WakeGate({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<"waking" | "ready" | "down">("waking");

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const ctl = new AbortController();
        const t = setTimeout(() => ctl.abort(), 3500);
        const r = await fetch(`${API}/api/health`, { cache: "no-store", signal: ctl.signal });
        clearTimeout(t);
        if (r.ok) {
          if (alive) setState("ready");
          return;
        }
      } catch {}
      const ok = await wakeBackend();
      if (alive) setState(ok ? "ready" : "down");
    })();
    return () => {
      alive = false;
    };
  }, []);

  if (state === "ready") return <>{children}</>;
  return (
    <main className="mx-auto flex min-h-dvh max-w-lg flex-col items-center justify-center px-6 text-center">
      <div className="text-2xl font-bold tracking-tight">
        FINN<span className="text-accent">.</span>
      </div>
      {state === "waking" ? (
        <>
          <p className="mt-3 animate-pulse text-sm text-zinc-500">Waking FINN up…</p>
          <p className="mt-1 text-[11px] text-zinc-600">free tier cold start · usually 30–60s</p>
          <div className="mt-5 h-1 w-40 overflow-hidden rounded-full bg-zinc-200 dark:bg-ink-800">
            <div className="h-full w-1/3 animate-pulse rounded-full bg-accent" />
          </div>
        </>
      ) : (
        <>
          <p className="mt-3 text-sm text-rose-400">FINN is unreachable right now.</p>
          <button className="btn-primary mt-4" onClick={() => location.reload()}>
            Retry
          </button>
        </>
      )}
    </main>
  );
}

export function SnapshotBanner() {
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    apiHealth().catch(() => {});
    async function apiHealth() {
      try {
        const r = await fetch(`${API}/api/health`, { cache: "no-store" });
        const d = await r.json();
        const nse = d?.sources?.nse_announcements;
        if (nse?.mode === "snapshot") {
          setMsg(`Live NSE unreachable from the cloud — showing committed snapshot as of ${nse.last_ok_at || "last build"}.`);
        }
      } catch {}
    }
  }, []);
  if (!msg) return null;
  return (
    <div className="mb-3 rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-[11px] leading-snug text-amber-400">
      {msg}
    </div>
  );
}
