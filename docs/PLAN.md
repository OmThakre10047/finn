# FINN — Financial Investment Agent · Build Plan (v1.2, locked)

ENAM "FINN — Financial Investment Agent" AI Engineer Build Challenge. Deadline: **15 Nov 2026 (today)**.
Deliverable: mobile-first working prototype + GitHub repo + AI build history + covering note.

## 0. Verified data-source strategy (probed from this machine, 15 Nov)

| Source | Probe result | Role |
|---|---|---|
| NSE announcements API | **BLOCKED via curl/plain TLS (403/301) but HTTP 200 via `curl_cffi` chrome impersonation** (20 records, fields: symbol, desc, attchmntText, attchmntFile, an_dt…) | **CORE** — live ingest via `curl_cffi` session with cookie warm-up |
| BSE announcements API | 403 even with Chrome-TLS impersonation | STRETCH (skip) |
| BSE PDF host (`AnnPdfOpen.aspx` → 302 → `xml-data/corpfiling/AttachLive/*.pdf`) | **HTTP 200, `%PDF-` verified** | **CORE** — filing PDF fetch fallback |
| screener.in company pages | HTTP 200; Quarterly/P&L/BS/CashFlow/Ratios/Documents tables all present; doc links → BSE PDF host + IR sites | **CORE** — fundamentals + documents index |
| yfinance (v8 chart) | HTTP 200; 22 daily bars for RELIANCE.NS | **CORE** — EOD price/volume |
| Gemini / Tavily | keys held by user, not in chat/session | CORE |

**Fallback discipline:** every live fetch degrades to a committed snapshot (`backend/data/snapshots/`); `/api/health` reports live-vs-snapshot per source. If cloud blocks NSE, snapshot serves the demo and BSE PDF host remains reachable for deep enrichments.

## 1. Architecture

```
┌─────────────────── Vercel — Next.js App Router + Tailwind (PWA) ───────────────────┐
│  Mobile-first: DIGEST (hero) | ALERTS | RESEARCH (ticker box) | SETTINGS            │
│  Dark/light toggle · installable · refresh fires POST /api/refresh on app open     │
└──────────────────────────────────┬─────────────────────────────────────────────────┘
                                   │ HTTPS JSON
┌──────────────────────────────────▼──── Render free tier — FastAPI (py3.10) ────────┐
│  Routers: /digest /alerts /research/{ticker} /portfolio /settings /refresh         │
│           /health (source_state) /admin/costs (cost ledger)                        │
│  Pipeline (asyncio jobs):                                                          │
│   ├─ ingest     NSE announcements (curl_cffi chrome session) → snapshot fallback   │
│   ├─ classify   RULES/KEYWORDS FIRST on NSE category+subject (free, log % rules-  │
│   │             handled) → cheap LLM batch ONLY for leftovers                      │
│   ├─ enrich     results PDF → metrics card (cheap-first, strong fallback)          │
│   │             mgmt-change → Tavily → cheap bio                                   │
│   ├─ market     yfinance EOD bars → volume (N×20d avg) + price (±X%) rules        │
│   └─ research   screener docs → latest AR + last 4–5 concalls + quarterly actuals │
│                 → chunk → cheap extract → strong synthesis → 8 sections +          │
│                 Promise Tracker (every claim cited {doc, period, page})            │
│  LLM Router: env-only model names (LLM_CHEAP/LLM_STRONG) · JSON mode · retry ·     │
│              llm_cache + COST LEDGER (task, model, tokens, cache_hit)              │
│  SQLite (single file): data + cache + llm_cache + llm_calls                        │
└────┬───────────────┬────────────────┬────────────────┬─────────────────────────────┘
     │               │                │                │
  NSE (curl_cffi)  yfinance      screener.in      Gemini / Tavily
  BSE PDF host   (EOD bars)    (BS4, cached HTML)  (external APIs)
```

## 2. Modules (backend/)

| Module | Job |
|---|---|
| `app/config.py` | env settings; model names ONLY from env |
| `app/db.py` | SQLite schema + access |
| `app/nse_client.py` | curl_cffi chrome-impersonated session; announcements; PDF download (NSE nsearchives + BSE AttachLive fallback) |
| `app/snapshot.py` | committed snapshot loader/saver; source_state |
| `app/market.py` | yfinance EOD bars, 20-day avg volume, ±X% moves |
| `app/screener.py` | company page scrape (cached HTML): financials tables, Documents section (AR + concall links) |
| `app/llm.py` | router (cheap/strong), JSON mode, retries+fallback, llm_cache, cost ledger rows |
| `app/classifier.py` | rules/keywords on NSE category+subject first → LLM batch leftovers; logs % rules-handled |
| `app/enrich_results.py` | page-select results statement → cheap extraction first; strong only on sanity-check failure; Python does ALL arithmetic (QoQ/YoY/margins/derived EBITDA) |
| `app/enrich_bio.py` | extract incoming person → Tavily → cheap summary bio |
| `app/research.py` | chunk AR + last 4–5 concalls → cheap per-chunk extraction (cited) → strong synthesis → 8 sections + Promise Tracker; drops uncited claims in code |
| `app/alertrules.py` | threshold engine → alerts table |
| `scripts/list_models.py` | lists models the Gemini key can actually use → pick LLM_CHEAP/LLM_STRONG |

## 3. Data model (SQLite, one file)

- `portfolio(id, ticker, exchange, name, is_active)`
- `watch_types(key, label, is_enabled)` — seeded from the reference doc's 17 categories
- `alert_settings(volume_mult, price_move_pct, window_hours)` — single row, user-editable
- `announcements(id, ticker, headline, nse_category, subject, category, materiality, priority, pdf_url, published_at, raw_json, summary, rules_handled)`
- `renders(announcement_id, kind: results_card|bio, payload_json)`
- `price_bars(ticker, date, open, high, low, close, volume)`
- `alerts(id, ticker, type: material|volume|price, payload_json, severity, created_at)`
- `filings(id, ticker, kind: ar|concall|results, url, period, path, content_hash, fetched_at)`
- `chunks(filing_id, idx, text, page)`
- `research_reports(ticker, status, payload_json, generated_at, expires_at)`
- `llm_cache(key_hash, model, response_json, created_at, hits)`
- `llm_calls(id, task, model, prompt_tokens, completion_tokens, cache_hit, created_at)` — **cost ledger** → `GET /api/admin/costs`

## 4. API

- `GET /api/health` — per-source `live|snapshot|error` + last fetch
- `GET/POST/DELETE /api/portfolio`
- `GET /api/digest?window=24h` → `{material: [...], routine: [...], stats: {rules_handled_pct, window}}` — material expanded, routine collapsed one-liners
- `POST /api/settings/alerts` · `GET/POST /api/settings/watch-types`
- `GET /api/alerts?since=`
- `POST /api/refresh` — ingest+classify+market (cron ping + frontend open)
- `POST /api/research/{ticker}` → 202 (or cached) · `GET /api/research/{ticker}` — 8 sections + Promise Tracker, citations inline
- `GET /api/admin/costs` — cost ledger (task, model, tokens, cache_hit %)

## 5. LLM routing (cheap-first, efficiency = graded bonus)

| Task | Route | Why |
|---|---|---|
| Classify announcements | **rules/keywords free** on NSE category+subject → **CHEAP batch** only for leftovers; log % handled without LLM | Volume task; NSE's own category labels do most work |
| Routine one-liners | CHEAP | Bulk |
| Results metrics extraction | **CHEAP on page-selected pages** → sanity checks (column echo, arithmetic coherence) → **STRONG only on failure** | Number fidelity where it matters, spend almost nothing |
| All QoQ/YoY/margins/derived EBITDA | **Python, never the LLM** | Exactness |
| Bio from Tavily content | CHEAP | Summarisation |
| Concall chunk promise extraction | CHEAP per chunk, citations required | Bulk; uncited claims dropped in code |
| Promise Tracker alignment + verdicts | STRONG | Cross-source reasoning |
| Bull/bear + research synthesis | STRONG | Multi-input reasoning |

Model names live ONLY in env (`LLM_CHEAP`, `LLM_STRONG`). Selection procedure: run `scripts/list_models.py` against the user's key, prefer a flash-lite tier for CHEAP; set env accordingly (local + Render).

## 6. Caching strategy

1. `llm_cache` on (model + normalised prompt) — classification, extraction, bio, sections.
2. Batching: ~20 announcements per LLM call; rules-first removes most calls entirely.
3. Data caches in SQLite: announcements, bars, filings, chunks, screener HTML; research reports expire ~24h.
4. Chunking ~800 tokens w/ overlap; only results-statement pages reach any LLM.
5. Render cold-start: frontend fires `/api/refresh`; snapshot keeps demo alive while fetches retry.

## 7. Build order

**CORE (today):** ① repo+docs+briefs ✅ → ② backend scaffold+schema+health → ③ NSE ingest (curl_cffi) + snapshot + 18-ticker seed → ④ yfinance bars + alert rules → ⑤ LLM router+cache+cost ledger+list_models+rules-first classifier → ⑥ digest endpoint → ⑦ results card → ⑧ Tavily bio → ⑨ research pipeline (AR + last 4–5 concalls + quarterly actuals; 8 sections; Promise Tracker w/ citations) → ⑩ frontend (Digest/Alerts/Research/Settings, theme toggle, PWA) → ⑪ deploy Render+Vercel, pre-warm research caches for all 5 ad-hoc tickers into committed snapshot → ⑫ polish + E2E smoke.

**STRETCH:** free-form Ask-FINN chat · BSE announcements coverage · web-push · Promise Tracker chart · alert-history UI.

**Portfolio (18):** RELIANCE, TCS, HDFCBANK, INFY, ITC, TATAMOTORS, MARUTI, SUNPHARMA, DRREDDY, TITAN, ADANIENT, DLF, TATAPOWER, BEL, PERSISTENT, ASTRAL, POLYCAB, IRCTC.
**Ad-hoc (5, ALL outside portfolio → proves generalisation):** ETERNAL, DMART, KPITTECH, CDSL, VARUNBEV.

## 8. Risks → status after probes

| # | Risk | Status |
|---|---|---|
| 1 | NSE API blocks | **Mitigated locally** via curl_cffi; snapshot still committed; test from Render early |
| 2 | Screener HTML drift | Mitigated (all tables confirmed); cache HTML; defensive parsing |
| 3 | Concall PDFs scans/unavailable | pdfplumber→pypdf fallback; honest "unavailable" state |
| 4 | Gemini rate limits | Cache-everything, batch, rules-first, cheap-fallback on 429 |
| 5 | Results extraction errors | Cheap-first + sanity checks → strong only on failure; Python arithmetic |
| 6 | Render free tier sleeps/no cron | Frontend-open refresh + external cron ping; snapshot demo mode |
| 7 | yfinance throttle | Once-daily EOD + SQLite cache |
| 8 | Cloud IPs blocked for NSE | De-risk at step 11 first thing; snapshot is the guarantee |
| 9 | Promise/quarter mis-alignment | Strict {doc, period, page} citations; uncited claims dropped in code |

## 9. Submission checklist

- [ ] Deployed mobile link (Vercel + Render)
- [ ] GitHub repo pushed (fix local git identity before push!)
- [ ] opencode build-history export (user-owned; keep sessions intact)
- [ ] Covering email → assessment@enam.com, subject **"IIT Delhi – AI Engineer - 2027"**: what we built, key decisions/trade-offs, deliberate omissions, next steps — quote cost-ledger numbers from `/api/admin/costs`

## 10. Working rules

- After EVERY step: dated `docs/PROGRESS.md` entry + git commit.
- Secrets never enter chat/session (graded artifact). `.env.example` names only.
- `AGENTS.md` carries stack/map/run/rules for agents.
