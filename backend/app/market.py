import json

from .db import get_db, get_source_state, set_source_state


def fetch_bars(tickers: list[str], period_days: int = 40) -> dict:
    import yfinance as yf

    out = {}
    for t in tickers:
        try:
            hist = yf.Ticker(f"{t}.NS").history(period=f"{period_days}d", interval="1d", auto_adjust=False)
            if hist.empty:
                hist = yf.Ticker(f"{t}.BO").history(period=f"{period_days}d", interval="1d", auto_adjust=False)
            out[t] = [
                {
                    "date": str(idx.date()),
                    "open": round(float(r["Open"]), 2),
                    "high": round(float(r["High"]), 2),
                    "low": round(float(r["Low"]), 2),
                    "close": round(float(r["Close"]), 2),
                    "volume": int(r["Volume"]),
                }
                for idx, r in hist.iterrows()
            ]
        except Exception:
            out[t] = []
    return out


def store_bars(bars: dict) -> int:
    n = 0
    with get_db() as conn:
        for ticker, rows in bars.items():
            for r in rows:
                cur = conn.execute(
                    """INSERT OR REPLACE INTO price_bars (ticker, date, open, high, low, close, volume)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (ticker, r["date"], r["open"], r["high"], r["low"], r["close"], r["volume"]),
                )
                n += cur.rowcount
    return n


def run_market_rules(volume_mult: float, price_move_pct: float) -> list[dict]:
    return backfill_market_alerts(volume_mult, price_move_pct, latest_only=True)


def backfill_market_alerts(volume_mult: float, price_move_pct: float, latest_only: bool = False) -> list[dict]:
    """Apply rules over stored bars. latest_only: just the most recent bar; else all stored days (~30d)."""
    fired = []
    with get_db() as conn:
        tickers = [r["ticker"] for r in conn.execute("SELECT DISTINCT ticker FROM price_bars")]
        for t in tickers:
            rows = [dict(r) for r in conn.execute(
                "SELECT date, close, volume FROM price_bars WHERE ticker = ? ORDER BY date ASC", (t,)
            )]
            if latest_only:
                rows = rows[-21:]
            for i in range(20, len(rows)):
                latest = rows[i]
                prev = rows[i - 1]
                avg20 = sum(rows[j]["volume"] for j in range(i - 20, i)) / 20.0
                if avg20 > 0 and latest["volume"] >= volume_mult * avg20:
                    fired.append({
                        "ticker": t, "type": "volume", "severity": "warning",
                        "payload": {"date": latest["date"], "volume": latest["volume"], "avg20": round(avg20), "ratio": round(latest["volume"] / avg20, 2)},
                    })
                if prev["close"] > 0:
                    move = 100.0 * (latest["close"] - prev["close"]) / prev["close"]
                    if abs(move) >= price_move_pct:
                        fired.append({
                            "ticker": t, "type": "price",
                            "severity": "warning" if abs(move) < 2 * price_move_pct else "critical",
                            "payload": {"date": latest["date"], "move_pct": round(move, 2), "close": latest["close"], "prev_close": prev["close"]},
                        })
        for a in fired:
            key = f"{a['ticker']}|{a['type']}|{a['payload']['date']}"
            conn.execute(
                "INSERT OR IGNORE INTO alerts (ticker, type, payload_json, severity, dedupe_key) VALUES (?, ?, ?, ?, ?)",
                (a["ticker"], a["type"], json.dumps(a["payload"]), a["severity"], key),
            )
    return fired


def backfill_material_alerts(watch_types: dict[str, bool], days: int = 30) -> int:
    """Material-announcement alerts for watched categories from the digest window."""
    n = 0
    with get_db() as conn:
        rows = conn.execute(
            """SELECT ticker, category, headline, subject, summary, published_at FROM announcements
               WHERE materiality = 'material' AND published_at >= datetime('now', ?)""",
            (f"-{days} days",),
        ).fetchall()
        for r in rows:
            if not watch_types.get(r["category"]):
                continue
            key = f"{r['ticker']}|material|{(r['published_at'] or '')[:10]}|{(r['headline'] or '')[:40]}"
            cur = conn.execute(
                """INSERT OR IGNORE INTO alerts (ticker, type, payload_json, severity, dedupe_key)
                   VALUES (?, 'material', ?, 'info', ?)""",
                (r["ticker"], json.dumps({
                    "category": r["category"], "headline": r["headline"], "summary": r["summary"],
                    "date": (r["published_at"] or "")[:10],
                }), key),
            )
            n += cur.rowcount
    return n


def refresh_market(tickers: list[str]) -> dict:
    bars = fetch_bars(tickers)
    stored = store_bars(bars)
    ok = sum(1 for v in bars.values() if v)
    set_source_state("yfinance", "live" if ok else "snapshot", None if ok else "no bars fetched")
    return {"tickers": len(tickers), "with_bars": ok, "bars_stored": stored}


def market_status() -> dict:
    return get_source_state("yfinance")
