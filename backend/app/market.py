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
    alerts = []
    with get_db() as conn:
        tickers = [r["ticker"] for r in conn.execute("SELECT DISTINCT ticker FROM price_bars")]
        for t in tickers:
            rows = conn.execute(
                "SELECT date, close, volume FROM price_bars WHERE ticker = ? ORDER BY date DESC LIMIT 21", (t,)
            ).fetchall()
            if len(rows) < 21:
                continue
            latest = rows[0]
            prev = rows[1]
            avg20 = sum(r["volume"] for r in rows[1:21]) / 20.0
            if avg20 > 0 and latest["volume"] >= volume_mult * avg20:
                alerts.append({
                    "ticker": t, "type": "volume", "severity": "warning",
                    "payload": {"date": latest["date"], "volume": latest["volume"], "avg20": round(avg20), "ratio": round(latest["volume"] / avg20, 2)},
                })
            if prev["close"] > 0:
                move = 100.0 * (latest["close"] - prev["close"]) / prev["close"]
                if abs(move) >= price_move_pct:
                    alerts.append({
                        "ticker": t, "type": "price", "severity": "warning" if abs(move) < 2 * price_move_pct else "critical",
                        "payload": {"date": latest["date"], "move_pct": round(move, 2), "close": latest["close"], "prev_close": prev["close"]},
                    })
        for a in alerts:
            conn.execute(
                """INSERT INTO alerts (ticker, type, payload_json, severity)
                   SELECT ?, ?, ?, ?
                   WHERE NOT EXISTS (
                     SELECT 1 FROM alerts WHERE ticker = ? AND type = ? AND payload_json = ?
                   )""",
                (a["ticker"], a["type"], json.dumps(a["payload"]), a["severity"], a["ticker"], a["type"], json.dumps(a["payload"])),
            )
    return alerts


def refresh_market(tickers: list[str]) -> dict:
    bars = fetch_bars(tickers)
    stored = store_bars(bars)
    ok = sum(1 for v in bars.values() if v)
    set_source_state("yfinance", "live" if ok else "snapshot", None if ok else "no bars fetched")
    return {"tickers": len(tickers), "with_bars": ok, "bars_stored": stored}


def market_status() -> dict:
    return get_source_state("yfinance")
