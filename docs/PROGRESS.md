# PROGRESS

## 2026-11-15 — Step 1 complete: repo init, briefs ingested, plan locked (v1.2)
- Probed all data sources from this machine (raw results in `docs/PLAN.md` §0):
  - NSE announcements API: 403/301 via curl+python TLS → **200 via curl_cffi chrome impersonation** (20 records). Live ingest = CORE.
  - BSE announcements API: 403 even with chrome TLS → STRETCH.
  - BSE PDF host: AnnPdfOpen.aspx → 302 → AttachLive PDF, HTTP 200, `%PDF-` verified. PDF fetch = CORE.
  - screener.in RELIANCE: 200, all financial tables + Documents present.
  - yfinance: 200, 22 daily bars for RELIANCE.NS.
- Copied both challenge PDFs to `docs/brief/`, extracted `main.txt` (9,515 chars) + `reference.txt` (7,975 chars) with pypdf; both read in full.
- Wrote `docs/PLAN.md` v1.2 (probe-informed ingest strategy, cheap-first routing, cost ledger, Promise Tracker citation rule, submission checklist).
- Wrote `AGENTS.md` (stack, map, run, agent rules) and `backend/.env.example` (names only — secrets never enter this session).
- User decisions locked: 18-stock portfolio + 5 ad-hoc tickers (all outside portfolio), Python 3.10 pinned, research screen is CORE (chat = STRETCH), dark+light theme toggle.
- Note: git identity set repo-locally as "Om Ravindra Thakre" <om-thakre@users.noreply.github.com> — **user must correct before pushing to GitHub**.
- Next: Step 2 — backend scaffold (FastAPI + SQLite schema incl. llm_calls cost ledger + /api/health).
