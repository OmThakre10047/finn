# FINN — Financial Investment Agent

Mobile-first triage for a public-markets investor. **Push**: a windowed digest of all NSE announcements across an 18-stock portfolio (material surfaced, routine buried) plus threshold alerts (volume ≥ N× 20-day average, price ±X%, watched announcement categories — all configurable with a live "would have fired N times" preview). **Pull**: on-demand research on ANY NSE ticker, grounded only in primary sources (annual report + concall transcripts via screener.in), with a **Promise Tracker** (what management promised vs what actually delivered, cited page-by-page).

> ENAM "FINN — AI Engineer Build Challenge" · Nov 2026

## Live

- **App**: https://finn-<your-alias>.vercel.app _(updated at deploy)_
- **API**: https://finn-api.onrender.com/api/health

## Screens

- **Today** — answers "is there anything I must act on?" in one line. MUST KNOW cards (results with Revenue/EBITDA/PBT/PAT + QoQ/YoY + filing page refs; management changes with sourced bios), WORTH A LOOK rows, ROUTINE collapsed. Tap anything → bottom sheet with the filing PDF.
- **Radar** — you decide what "unusual" means: threshold sliders with a live "would have fired N times in 30 days" backtest, category toggles, and fired alerts with price/volume charts and the threshold line drawn.
- **Research** — type any NSE symbol; FINN reads the annual report + last 4 concalls (whole documents, page-cited) and returns 8 sections plus the Promise Tracker with a credibility score. Footer: "Built from N primary documents · 0 news · ₹0".

## Architecture

```
Next.js (Vercel, PWA)  →  FastAPI (Render free tier)  →  NSE (curl_cffi TLS-impersonated)
                                    │                    screener.in · yfinance · Gemini · Tavily
                            SQLite single file
                    (data + llm cache + cost ledger + snapshot restore)
```

- **Cheap-first LLM routing**: regex/keyword rules classify ~70% of announcements free; `LLM_CHEAP` (flash-lite) batch-handles leftovers and does bulk extraction; `LLM_STRONG` (flash) only for synthesis and results verification retries. All arithmetic (QoQ/YoY/margins, EBITDA derivation, verdicts on numeric targets) is Python, never the model.
- **Caching**: SHA-keyed `llm_cache`, batched classification, document-level extraction (1M-token input window fits a full transcript), 24h research reports, committed snapshot.
- **Cost ledger**: every call logged (task, model, tokens, cache-hit) → `GET /api/admin/costs`.
- **Resilience**: NSE blocks most cloud IPs → a committed snapshot (announcements, renders, alerts, research reports) auto-restores on boot; the UI says "as of <snapshot time>" when live NSE is unreachable.

## Run locally

```bash
# backend (Python 3.10)
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && cp .env.example .env   # add your keys
uvicorn app.main:app --reload --port 8000
# frontend
cd frontend && npm install && npm run dev   # NEXT_PUBLIC_API_BASE_URL defaults to localhost:8000
```

`make refresh` runs the full pipeline and refreshes the committed snapshot. `make test` runs the data-pipeline test suite (18 checks on real filings).

## Deploy

- **Backend (Render)**: New → Blueprint → pick this repo (`render.yaml`). Set env vars: `GEMINI_API_KEY`, `TAVILY_API_KEY`, `LLM_CHEAP`, `LLM_STRONG`, `ALLOWED_ORIGINS` (your Vercel domain). Free tier sleeps — first request wakes it (~30-60s).
- **Frontend (Vercel)**: import the repo, set `NEXT_PUBLIC_API_BASE_URL` to the Render URL.

## Docs

`docs/PLAN.md` (architecture, data model, LLM routing table, risks) · `docs/PROGRESS.md` (full build log) · `docs/brief/` (challenge briefs) · `docs/screens/` (design artifacts).
