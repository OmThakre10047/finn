# DECISIONS.md — key decisions, trade-offs, omissions, next steps

## What we built and why

**Rules-first classification.** NSE's own announcement headers ("Change in Director(s)", "Outcome of Board Meeting"…) are standardised, so 17 curated regex rules classify ~70% of the feed free; only ambiguous leftovers ("General Updates", "Press Release") go to a batched cheap-LLM call. Every run logs the % handled without the LLM. Trade-off: rules need maintenance as NSE phrasing drifts; the LLM batch is the safety net.

**Cheap-first LLM routing.** `LLM_CHEAP` (flash-lite) does bulk work — classification leftovers, per-document extraction, bios; `LLM_STRONG` (flash, thinking budget capped) only synthesises research sections/verdicts and re-checks results numbers when sanity checks fail. Over the build, 84 of 100 calls were cheap (84%), ~644k input / 67k output tokens total, 22% cache hits. The whole product runs on free tiers.

**Python does all arithmetic.** QoQ, YoY, margins, EBITDA derivation (PBT + finance cost + depreciation), and verdicts on numeric promise targets are computed in code from extracted absolutes. The model reads tables; it never does math. Sanity gates (rows present, |Δ| bounds, PAT ≤ PBT, PAT < Revenue, known currency units) reject bad extractions and trigger a strong-model retry.

**Numbers are verified against page text.** Every extracted "current" value must appear in the selected filing page text (comma/decimal normalised) before it's shown, with its page number rendered. Rows that fail are dropped; fewer than three survivors means no card. Scanned PDFs get a vision fallback and are labelled "from scanned page N" — and if a filing is a newspaper ad or a presentation deck (common!), the app honestly shows nothing.

**Citation validation in code.** Research synthesis must cite {doc, period, page}; code drops any citation whose doc wasn't actually extracted or whose page wasn't sent. Promise Tracker rows with no surviving citations are dropped. Sections render with error boundaries so one bad section can't kill a report.

**Whole-document extraction, not BM25 chunks.** Flash-lite's 1M-token input fits an entire concall transcript (or a page-selected slice of an annual report) in one call, so a report costs ~5 extraction calls + 2 synthesis calls instead of dozens of RAG chunks. Annual-report pages are chosen by a heading index (business/MD&A, segments, balance sheet, cash flow, borrowings, contingent liabilities, related-party, auditor — the last three always included), split into ~60k-token call budgets.

**Snapshot mode.** NSE blocks most cloud IPs (Akamai), so every live fetch degrades to a committed snapshot (232 announcements + renders + alerts + 6 research reports) that auto-restores on boot. Render's ephemeral disk wipes the DB on restart anyway, so the snapshot is both the demo guarantee and the persistence layer. Verified live: NSE *is* currently reachable from Render, but the fallback costs nothing.

**Honest states.** "No card" for newspaper/scanned filings, "Not enough checkable promises" instead of a fake credibility %, "unverifiable" verdicts when actuals don't cover a quarter, "No reliable public profile found" for bios, "Couldn't render this section" error boundaries.

## Deliberately left out

- **Free-form chat** — the ticker-box research covers the pull story with better grounding per minute spent.
- **Web push / email digests** — in-app triage + a refresh ping covers the demo; push needs a queue and permissions.
- **BSE announcements** — its API is Akamai-blocked even with TLS impersonation; BSE's PDF host (used for all filings) and screener remain in.
- **Voice** — no time, no signal for the graded workflows.
- **Vector DB / embeddings** — whole-doc extraction made them unnecessary; that's a next-step if reports go multi-company.

## Where next

Cross-company Promise Tracker (portfolio-level "who keeps their word"), charted trajectory + promise timelines, alert delivery (push/email), BSE via the PDF host's filing index, a vector layer over the chunked filings for ad-hoc questions with the same citation discipline, and Postgres + persistent disk on Render so the cost ledger survives restarts.
