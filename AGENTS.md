# AGENTS.md — FINN

Financial Investment Agent for the ENAM build challenge (deadline 15 Nov 2026). Mobile-first prototype: PUSH (digest + alerts) and PULL (grounded research with Promise Tracker).

## Stack
- **backend/**: Python 3.10 (pinned — local == Render), FastAPI, SQLite single file, httpx, `curl_cffi` (NSE needs Chrome TLS impersonation), yfinance, pypdf, BeautifulSoup4.
- **frontend/**: Next.js App Router + TypeScript + Tailwind, mobile-first, installable PWA, dark/light toggle.
- **LLM**: Google Gemini via google-genai behind our own router (`app/llm.py`). Model names ONLY in env: `LLM_CHEAP`, `LLM_STRONG` (see `backend/.env.example`; run `scripts/list_models.py` to list usable models). Tavily for people bios.
- Deploy: Vercel (frontend) + Render free tier (backend). NSE blocks most cloud IPs → committed snapshot fallback is mandatory.

## Folder map
```
docs/brief/      challenge PDFs + extracted text (main.txt, reference.txt)
docs/PLAN.md     locked plan v1.2 (architecture, schema, routing, risks)
docs/PROGRESS.md dated log — append after EVERY step, then git commit
backend/         FastAPI app (see PLAN §2 modules), data/finn.db, data/snapshots/
frontend/        Next.js app
scripts/         utility scripts (list_models.py, seed, prewarm)
```

## Run
```bash
# backend
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && cp .env.example .env   # user fills .env (NEVER paste secrets in chat)
uvicorn app.main:app --reload --port 8000
# frontend
cd frontend && npm install && npm run dev
```

## Rules for agents
1. Cheap-first everywhere: rules/keywords before any LLM call; cheap model before strong; strong only on sanity-check failure. Log % handled without LLM.
2. Python does ALL arithmetic (QoQ, YoY, margins, derived EBITDA) — never the LLM.
3. Research/pull is grounded ONLY in primary sources (AR + concall transcripts via screener.in links). Every claim carries {doc, period, page}; code drops uncited claims. No news/broker notes/model memory on the pull side.
4. Promise Tracker uses latest AR + last 4–5 concalls + screener quarterly table for actuals.
5. Every live fetch degrades to committed snapshot; never let the UI go empty.
6. Secrets never enter chat/session history (it is part of the submission). `.env` is gitignored.
7. After every step: append dated entry to docs/PROGRESS.md and make a git commit.
8. Ad-hoc research set (ETERNAL, DMART, KPITTECH, CDSL, VARUNBEV) is intentionally outside the portfolio to prove generalisation; pre-warm their caches into the snapshot before demo.
