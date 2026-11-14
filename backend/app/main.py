from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .config import ALLOWED_ORIGINS, DEFAULT_ALERT_SETTINGS, LLM_CHEAP, LLM_STRONG, PORTFOLIO, WATCH_TYPES
from .db import get_db, get_source_state

app = FastAPI(title="FINN API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SOURCES = ["nse_announcements", "bse_pdfs", "screener", "yfinance", "gemini", "tavily"]


@app.on_event("startup")
def startup() -> None:
    db.init_db()
    with get_db() as conn:
        if conn.execute("SELECT COUNT(*) c FROM portfolio").fetchone()["c"] == 0:
            conn.executemany(
                "INSERT OR IGNORE INTO portfolio (ticker, exchange) VALUES (?, 'NSE')",
                [(t,) for t in PORTFOLIO],
            )
        if conn.execute("SELECT COUNT(*) c FROM watch_types").fetchone()["c"] == 0:
            conn.executemany(
                "INSERT OR IGNORE INTO watch_types (key, label, is_enabled) VALUES (?, ?, ?)",
                [(k, k.replace("_", " ").title(), v) for k, v in WATCH_TYPES.items()],
            )
        if conn.execute("SELECT COUNT(*) c FROM alert_settings").fetchone()["c"] == 0:
            conn.execute(
                "INSERT INTO alert_settings (id, volume_mult, price_move_pct, window_hours) VALUES (1, ?, ?, ?)",
                (DEFAULT_ALERT_SETTINGS["volume_mult"], DEFAULT_ALERT_SETTINGS["price_move_pct"], DEFAULT_ALERT_SETTINGS["window_hours"]),
            )


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": app.version,
        "llm_configured": bool(LLM_CHEAP and LLM_STRONG),
        "llm_models": {"cheap": LLM_CHEAP or None, "strong": LLM_STRONG or None},
        "sources": {s: get_source_state(s) for s in SOURCES},
    }


@app.get("/api/admin/costs")
def costs() -> dict:
    with get_db() as conn:
        total = conn.execute(
            "SELECT COUNT(*) calls, SUM(prompt_tokens) pt, SUM(completion_tokens) ct, SUM(cache_hit) cached FROM llm_calls"
        ).fetchone()
        by_task = conn.execute(
            """SELECT task, model, COUNT(*) calls, SUM(prompt_tokens) pt, SUM(completion_tokens) ct,
                      SUM(cache_hit) cached, SUM(CASE WHEN cache_hit = 0 THEN 1 ELSE 0 END) live_calls
               FROM llm_calls GROUP BY task, model ORDER BY calls DESC"""
        ).fetchall()
        by_model = conn.execute(
            """SELECT model, COUNT(*) calls, SUM(prompt_tokens) pt, SUM(completion_tokens) ct,
                      SUM(cache_hit) cached, SUM(CASE WHEN cache_hit = 0 THEN 1 ELSE 0 END) live_calls
               FROM llm_calls GROUP BY model ORDER BY calls DESC"""
        ).fetchall()
    t = dict(total)
    calls = t["calls"] or 0
    return {
        "totals": {**t, "cache_hit_pct": round(100 * (t["cached"] or 0) / calls, 1) if calls else 0.0},
        "by_task": [dict(r) for r in by_task],
        "by_model": [dict(r) for r in by_model],
    }
