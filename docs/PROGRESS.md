# PROGRESS

## 2026-11-15 — Step 5 (in progress): LLM router + cost ledger + rules-first classifier
- `app/llm.py`: Gemini router — env-only model names, JSON mode, 429/5xx retry w/ backoff, `llm_cache` (sha256 of model+task+prompt), cost ledger rows on every call (cache hits logged at 0 tokens, `cache_hit=1`).
- `app/classifier.py`: **rules-first** — 17 curated regex rules over NSE standard headers (desc) then subject; ambiguous headers ("General Updates", "Outcome of Board Meeting"…) go to cheap-LLM batch; priority scoring by category + watch-type boost + recency.
- `scripts/list_models.py`: dumps every model the user's key can use (input/output token limits) → pick LLM_CHEAP (prefer flash-lite) + LLM_STRONG; names stay in env only.
- **Live run: 14/16 (87.5%) classified FREE by rules**; 2 leftovers (DRREDDY/INFY "General Updates") await key. Spot-verified: IRCTC "Outcome of Board Meeting" = actual Q2FY27 financial results filing (ideal step-7 test case); HDFCBANK "General Updates" = RBI approval of Whole-time Director re-appointment → management_change ✓.

## 2026-11-15 — Step 4 complete: yfinance EOD bars + alert rules + settings/portfolio endpoints
- `app/market.py`: fetch (`.NS` → `.BO` fallback), store 40d of daily bars, rules engine (volume ≥ N×20-day avg; |move| ≥ ±X%; severity escalation at 2×X), dedup on (ticker,type,payload).
- Endpoints: `POST /api/refresh` (ingest + market + rules in one call), `GET/POST/DELETE /api/portfolio`, `GET/POST /api/settings/alerts`, `GET/POST /api/settings/watch-types`, `GET /api/alerts`.
- Live run: 17/18 tickers got bars (680 rows). TATAMOTORS returns 0 bars on Yahoo (post-demerger ticker change) → swapped to TATASTEEL (40 bars, close 186.68); portfolio + config updated.
- Rules engine proven: with tiny thresholds (0.0001) 33 alerts fired across tickers with correct math (e.g. ADANIENT −1.95%, vol ratio 0.71); test rows cleaned; natural thresholds fired 0 today (quiet Friday) — fine.
- API smoke: /api/portfolio lists 18 tickers; /api/alerts empty; /api/refresh returns ingest+market+alerts in one response.

## 2026-11-15 — Step 3 complete: NSE live ingest + snapshot fallback + PDF fetch
- `app/nse_client.py`: curl_cffi chrome124 session with homepage warm-up; 3 fetch strategies (GET+dates works: `from_date/to_date` dd-mm-yyyy); normalize (symbol/desc/attchmntText/attchmntFile/an_dt); PDF downloader (nsearchives direct + BSE AttachLive fallback, `%PDF-` magic check).
- `app/ingest.py`: ingest(days_back) → live fetch → save snapshot (portfolio rows only, 30KB committed) → upsert with UNIQUE dedup; on failure → snapshot mode + source_state.
- **Live result: 2,801 announcements over 3 days, 16 matched portfolio (HDFCBANK "Change in Director(s)", BEL order-win, RELIANCE concall notice…)**. Re-run inserted 0 (dedup verified).
- PDF download verified: ADANIENT media release 189,156 bytes, valid PDF from nsearchives.in.
- Endpoints: `POST /api/refresh`, `GET /api/announcements?window_hours=&ticker=`.

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
