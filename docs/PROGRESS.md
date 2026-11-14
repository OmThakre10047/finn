# PROGRESS

## 2026-11-15 — Step 2 complete: backend scaffold + SQLite schema + health/costs
- `backend/requirements.txt` (pinned; fastapi, curl_cffi, yfinance, pypdf, pdfplumber, bs4, google-genai, …), venv created, imports verified on Python 3.10.
- `app/config.py`: env-only settings; 18-ticker portfolio; 5 ad-hoc tickers; 17 watch-type defaults; alert defaults (2.0× vol, 4% move, 24h).
- `app/db.py`: full schema — portfolio, watch_types, alert_settings, announcements (+idx, dedup unique), renders, price_bars, alerts, filings, chunks, research_reports, llm_cache, **llm_calls (cost ledger)**, source_state. WAL mode.
- `app/main.py`: FastAPI + CORS; startup seeds portfolio/watch-types/settings; `GET /api/health` (per-source live|snapshot|error + LLM config state); `GET /api/admin/costs` (totals, cache-hit %, by-task, by-model).
- Smoke test on :8000 passed — health + costs return correct shapes; LLM shows unconfigured until user fills `.env`.

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
