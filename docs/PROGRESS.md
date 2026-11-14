# PROGRESS

## 2026-11-15 — Review-2 fixes 1-6 shipped; full chain run; snapshot enriched; costs ledger live
- **Fix 1 (ticker resolution)**: `screener.resolve_slug()` — direct slug → search-by-symbol → search-by-`sm_name` (from NSE feed) → prefix; cached in new `kv` table. Verified: VARUNBEV→**VBL**, HAPPSTMNDS→direct, SUPREMEIND→direct.
- **Fix 2 (synthesis robustness)**: split into two strong calls (sections; promise_tracker) via new `llm.call_json_strict` (max_output_tokens=24576, thinking_budget=1024, retries, and errors that name the failure — ETERNAL's root cause was a trailing ``` fence, now handled by `raw_decode`). ETERNAL: 8 sections + 11 tracker rows; VARUNBEV: 8 + 5.
- **Fix 3 (get_status)**: status column checked FIRST — error rows return `{status:'error', error}` with real message; UI shows "Research failed" + message + Retry button (POST restarts from error).
- **Fix 4 (AR section log)**: per-section page counts computed from pages actually kept in payloads. IRCTC AR 380p → 42 selected (6p/section × 7 sections incl. auditor_report, contingent_liabilities, related_party) in 1 payload under cap.
- **Fix 5 (Rs Cr normalisation)**: `_unit_to_crore_mult` (lakhs ÷100, Mn ×10, Rs ÷1e7) applied AFTER text-verification (matching stays against raw filing numbers). **BEL: 732,772 lakhs → 7,327.72 Rs Cr** (Revenue p8, PBT 2,054.11, PAT 1,540.37; QoQ +32.1%/+47.1%/+46.1%, YoY +26.5%/+18.9%/+19.7%).
- **Fix 6 (dedupe)**: one card per (ticker, period), keeps most verified rows; losers marked skipped. 16 raw → deduped.
- **make refresh**: root Makefile → `scripts/refresh_snapshot.py` (ingest→market→classify→enrich→snapshot). Snapshot now commits announcements + **research_reports.json (6 reports) + renders.json (39)**; `snapshot.restore_if_empty()` repopulates a fresh DB at startup (fresh-deploy demo resilience).
- **Costs (/api/admin/costs)**: 100 calls — 84 flash-lite / 16 flash (84% cheap routing), 644k in + 67k out tokens, 22% cache hits; strong model only for 6 syntheses + 5 results-verification retries.
- Frontend build green; research reports cover IRCTC + all 5 ad-hoc tickers (ETERNAL, DMART, KPITTECH, CDSL, VARUNBEV).

## 2026-11-15 — Review fixes 1-6 implemented + tested (17/17), model shortlist verified
- **Models (fix 1)**: `scripts/test_models.py` real calls — `gemini-3.5-flash-lite` OK (1.0s, clean JSON); `gemini-2.5-pro` **404 "no longer available to new users"** (2.5-flash too); `gemini-3.5-flash` OK (JSON + thinking 512 ≈ 12s). Final: `LLM_CHEAP=gemini-3.5-flash-lite`, `LLM_STRONG=gemini-3.5-flash` (flash non-lite per user rule).
- **Bios (fix 2)**: filing-first — read first 2 pages of the announcement PDF, extract person/role/incoming + `bio_in_filing` verbatim; filing bio wins (primary, free, source = PDF#page=1). Else Tavily with `person + company + role`; snippets must mention the company/ticker (code check) else honest "No reliable public profile found"; source URLs stored + rendered as chips.
- **AR (fix 3)**: no start-truncation. `_doc_pages` returns all pages; `_select_ar_pages` heading-index keeps business/MD&A/segment/BS/cash-flow/borrowings/contingent-liabilities/RPT/auditor pages (+2 after each); IRCTC AR 380p → 157 selected → exactly 2 call payloads, each ≤240k chars (~60k tokens). Transcripts >cap split into 2 calls at page boundaries.
- **Promise Tracker (fix 4)**: (a) concall periods from screener labels sorted by parsed date (Aug 2026 → Jul 2020, n=29); (b) `_validate_citations` — every citation's doc must map to an extracted doc and page must be in pages actually sent; invalid citations dropped from ALL sections; tracker rows with no valid citations dropped; (c) `_numeric_verdicts` — Python maps metric→screener row (sales growth/OPM%/PAT), resolves quarter_key→column, computes delivered + delivered/missed/partial (≥98%/≥90% of target); LLM verdict only for non-numeric or uncovered quarters. Synthesis schema now includes `quarter_key`.
- **Junk (fix 5)**: walrus block + `name = ratios.get(...)` gone; company name from screener h1 ("Indian Railway Catering & Tourism Corporation Ltd"); `_col_idx`/`verdict_code` cruft removed; main.py verified clean.
- **Results card (fix 6)**: `verify_rows` — every extracted `current` must appear in the selected page text (comma/space/decimal-normalized), per-row page number stored + rendered (`p.N` in label col); unfound rows dropped; <3 survivors → strong retry. **Real-data finds**: KAYNES SE-format statement (Rev 6,672.71 / PBT 1,270.17 / PAT 970.72 verified on p.7, fabricated number dropped); FUSIONCX press-deck + IRCTC scanned/newspaper correctly produce NO card (honest).
- `scripts/test_fixes.py`: **17/17 PASS** on real filings (7-day ingest: 3,907 market rows → 24 portfolio, dedup held).

## 2026-11-15 — Steps 7/8/9 built (awaiting LLM model env lines), ingest accounting clarified
- User sanity-check on "2,801 in 3 days" resolved: that is the WHOLE-MARKET NSE feed (fetch layer); stored/DB = 16 portfolio rows over 3 days (~0.3/stock/day, correct for large caps). Per-symbol counts + HDFCBANK subjects shown. Snapshot intentionally holds portfolio rows only (30KB).
- `list_models.py` ran against user's key: full catalog returned. Proposed: `LLM_CHEAP=gemini-3.5-flash-lite`, `LLM_STRONG=gemini-2.5-pro` (fallbacks: 2.5-flash-lite / 3.1-pro-preview). Names env-only per user rule.
- `app/enrich_results.py` (step 7): pypdf text + page-selector heuristic (results-statement keywords) → CHEAP extraction first → Python does ALL arithmetic (QoQ/YoY derived from absolutes; EBITDA = PBT+interest+depreciation if unstated) → sanity checks (rows present, |QoQ/YoY|<300%, PAT≤PBT×1.05) → STRONG retry only on failure. Renders cached per announcement.
- `app/enrich_bio.py` (step 8): CHEAP person/role extraction → Tavily search → CHEAP 2-3 sentence bio → render; negative results cached too.
- `app/research.py` (step 9): screener docs → latest AR + last 4 concalls → PDF cache w/ content hash → [[PAGE n]] markers → ONE cheap extraction call per doc (1M-token input fits whole transcript) → screener quarterly actuals (last 8 quarters) → STRONG synthesis (8 sections + Promise Tracker) → code drops uncited promise rows; verdicts delivered/missed/partial/unverifiable; report cached 24h in research_reports; threaded worker + poll endpoints.
- Endpoints: `POST/GET /api/research/{ticker}` (503 if LLM unconfigured, 404 if never started), `/api/refresh` now runs classify→results-card→bio chain.

## 2026-11-15 — Step 10 (scaffold) complete: frontend built + E2E smoke green
- Next.js 14 (App Router, TS, Tailwind), mobile-first max-w-lg, bottom tab bar (Digest/Alerts/Research/Settings), dark default + light toggle (localStorage + no-flash init script), installable PWA (manifest + generated 192/512 icons, standalone display).
- Digest hero: window chips (24h→30d), 3-stat strip (material / routine collapsed / % rules-handled free), expandable material cards with ResultsCard + BioCard renders + PDF link, routine collapsed by category.
- Research page: ticker box + 5 ad-hoc demo chips → POST + poll → 8 sections + Promise Tracker with citation chips. Alerts page: volume/price/material cards. Settings: threshold sliders, watch-type chips, portfolio add/remove.
- `npm run build` green (91KB first load); CORS preflight verified; E2E smoke (backend :8000 + next start :3000) passed.
- backend: digest renders now JSON-parsed server-side.

## 2026-11-15 — Step 6 complete: digest endpoint + screener.in client
- `app/digest.py`: window filter (parses NSE dates), material expanded / routine collapsed by category, stats incl. rules_pct; `GET /api/digest?window_hours=` live (7d: 16 items, 6 material, 87.5% rules-handled).
- `app/screener.py`: chrome-impersonated fetch; **documents parser reverse-engineered** (`div.documents.concalls` / `div.documents.annual-reports` blocks, period labels, BSE AttachHis/AnnPdfOpen links) — IRCTC: 29 concalls + 7 ARs; RELIANCE: 63 concalls + 14 ARs. Quarterly table parser: 12 quarters × Sales/OP/PBT/NP; top-ratios parsed (ROCE/ROE etc.).
- All filing PDFs confirmed on BSE hosts that serve PDFs.

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
