from datetime import datetime, timedelta
import json

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .config import ALLOWED_ORIGINS, DEFAULT_ALERT_SETTINGS, LLM_CHEAP, LLM_STRONG, PORTFOLIO, WATCH_TYPES
from .db import get_db, get_source_state
from .ingest import ingest
from . import market
from .config import ADHOC_TICKERS
from .digest import build_digest
from . import research


def _enrich_all() -> dict:
    from . import classifier, enrich_bio, enrich_results

    cs = classifier.classify_all()
    rc = enrich_results.enrich_results()
    bc = enrich_bio.enrich_bios()
    return {"classify": cs, "results_cards": rc, "bios": bc}

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
    from . import snapshot

    snapshot.restore_if_empty()
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


@app.post("/api/refresh")
def refresh(days_back: int = 3, enrich: bool = True) -> dict:
    ing = ingest(days_back)
    with get_db() as conn:
        s = dict(conn.execute("SELECT volume_mult, price_move_pct FROM alert_settings WHERE id = 1").fetchone())
    mk = market.refresh_market(PORTFOLIO)
    fired = market.run_market_rules(s["volume_mult"], s["price_move_pct"])
    enr = _enrich_all() if enrich else None
    return {"ingest": ing, "market": mk, "alerts_fired": fired, "enrich": enr}


@app.post("/api/research/{ticker}")
def research_start(ticker: str) -> dict:
    from . import llm

    if not llm.configured():
        raise HTTPException(503, "LLM not configured — set GEMINI_API_KEY + model names in backend/.env")
    return research.start(ticker)


@app.get("/api/research/{ticker}")
def research_get(ticker: str) -> dict:
    st = research.get_status(ticker)
    if st["status"] == "missing":
        raise HTTPException(404, f"No research started for {ticker.upper()} — POST first")
    return st


@app.get("/api/portfolio")
def portfolio_list() -> dict:
    with get_db() as conn:
        rows = [dict(r) for r in conn.execute("SELECT ticker, name, is_active FROM portfolio ORDER BY ticker")]
    return {"portfolio": rows, "adhoc_demo": ADHOC_TICKERS}


@app.post("/api/portfolio")
def portfolio_add(body: dict) -> dict:
    t = str(body.get("ticker", "")).upper().strip()
    if not t:
        raise HTTPException(400, "ticker required")
    with get_db() as conn:
        conn.execute("INSERT OR IGNORE INTO portfolio (ticker, exchange) VALUES (?, 'NSE')", (t,))
    return {"ok": True, "ticker": t}


@app.delete("/api/portfolio/{ticker}")
def portfolio_remove(ticker: str) -> dict:
    with get_db() as conn:
        conn.execute("DELETE FROM portfolio WHERE ticker = ?", (ticker.upper(),))
    return {"ok": True}


@app.get("/api/settings/alerts")
def get_alert_settings() -> dict:
    with get_db() as conn:
        return dict(conn.execute("SELECT * FROM alert_settings WHERE id = 1").fetchone())


@app.post("/api/settings/alerts")
def set_alert_settings(body: dict) -> dict:
    with get_db() as conn:
        for k, col in (("volume_mult", "volume_mult"), ("price_move_pct", "price_move_pct"), ("window_hours", "window_hours")):
            if k in body:
                conn.execute(f"UPDATE alert_settings SET {col} = ? WHERE id = 1", (body[k],))
        return dict(conn.execute("SELECT * FROM alert_settings WHERE id = 1").fetchone())


@app.get("/api/settings/watch-types")
def get_watch_types() -> dict:
    with get_db() as conn:
        return {"watch_types": [dict(r) for r in conn.execute("SELECT * FROM watch_types ORDER BY key")]}


@app.post("/api/settings/watch-types")
def set_watch_types(body: dict) -> dict:
    enabled = body.get("enabled", {})
    with get_db() as conn:
        for k, v in enabled.items():
            conn.execute("UPDATE watch_types SET is_enabled = ? WHERE key = ?", (1 if v else 0, k))
    return get_watch_types()


@app.get("/api/bars/{ticker}")
def bars(ticker: str, days: int = Query(30, ge=5, le=120)) -> dict:
    with get_db() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT date, close, volume FROM price_bars WHERE ticker = ? ORDER BY date DESC LIMIT ?", (ticker.upper(), days)
        )]
    rows.reverse()
    avg20 = None
    if len(rows) >= 21:
        avg20 = round(sum(r["volume"] for r in rows[-21:-1]) / 20.0)
    return {"ticker": ticker.upper(), "bars": rows, "avg20_volume": avg20}


@app.get("/api/alerts/preview")
def alerts_preview(volume_mult: float = Query(2.0, ge=0.1), price_move_pct: float = Query(4.0, ge=0.1)) -> dict:
    """Would-have-fired count over the stored ~30 days, for the Radar rules editor."""
    with get_db() as conn:
        tickers = [r["ticker"] for r in conn.execute("SELECT DISTINCT ticker FROM price_bars")]
    vol_fires, price_fires, examples = 0, 0, []
    for t in tickers:
        with get_db() as conn:
            rows = [dict(r) for r in conn.execute(
                "SELECT date, close, volume FROM price_bars WHERE ticker = ? ORDER BY date ASC", (t,)
            )]
        for i in range(20, len(rows)):
            avg20 = sum(rows[j]["volume"] for j in range(i - 20, i)) / 20.0
            if avg20 > 0 and rows[i]["volume"] >= volume_mult * avg20:
                vol_fires += 1
                if len(examples) < 6:
                    examples.append({"ticker": t, "type": "volume", "date": rows[i]["date"], "ratio": round(rows[i]["volume"] / avg20, 2)})
            if rows[i - 1]["close"] > 0:
                move = 100.0 * (rows[i]["close"] - rows[i - 1]["close"]) / rows[i - 1]["close"]
                if abs(move) >= price_move_pct:
                    price_fires += 1
                    if len(examples) < 6:
                        examples.append({"ticker": t, "type": "price", "date": rows[i]["date"], "move_pct": round(move, 2)})
    return {"volume_fires": vol_fires, "price_fires": price_fires, "total": vol_fires + price_fires, "examples": examples}


@app.get("/api/alerts")
def list_alerts(since_hours: int = Query(168, ge=1, le=24 * 30)) -> dict:
    cutoff = (datetime.utcnow() - timedelta(hours=since_hours)).isoformat(timespec="seconds")
    with get_db() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT id, ticker, type, payload_json, severity, created_at FROM alerts WHERE created_at >= ? ORDER BY created_at DESC LIMIT 200",
            (cutoff,),
        )]
    for r in rows:
        r["payload"] = json.loads(r.pop("payload_json"))
    return {"count": len(rows), "alerts": rows}


@app.get("/api/announcements")
def announcements(
    window_hours: int = Query(24, ge=1, le=24 * 30),
    ticker: str | None = None,
) -> dict:
    since = (datetime.utcnow() - timedelta(hours=window_hours)).isoformat(timespec="seconds")
    q = "SELECT id, ticker, headline, nse_category, subject, pdf_url, published_at, summary, materiality, category, priority FROM announcements WHERE published_at >= ?"
    params: list = [since]
    if ticker:
        q += " AND ticker = ?"
        params.append(ticker.upper())
    q += " ORDER BY published_at DESC LIMIT 500"
    with get_db() as conn:
        rows = [dict(r) for r in conn.execute(q, params)]
    return {"window_hours": window_hours, "count": len(rows), "items": rows}


@app.get("/api/digest")
def digest(window_hours: int = Query(24, ge=1, le=24 * 30), ticker: str | None = None) -> dict:
    return build_digest(window_hours, ticker)


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
