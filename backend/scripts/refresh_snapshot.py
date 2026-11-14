#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import market, snapshot
from app.classifier import classify_all
from app.config import PORTFOLIO
from app.enrich_bio import enrich_bios
from app.enrich_results import enrich_results
from app.ingest import ingest


def main() -> None:
    ing = ingest(3)
    print(f"ingest: {ing['mode']} fetched={ing['fetched']} inserted={ing['inserted']}")
    mk = market.refresh_market(PORTFOLIO)
    with __import__("app.db", fromlist=["get_db"]).get_db() as conn:
        s = dict(conn.execute("SELECT volume_mult, price_move_pct FROM alert_settings WHERE id = 1").fetchone())
    fired = market.run_market_rules(s["volume_mult"], s["price_move_pct"])
    print(f"market: {mk} | alerts fired: {len(fired)}")
    cs = classify_all()
    print(f"classify: {json.dumps(cs)}")
    rc = enrich_results()
    bc = enrich_bios()
    print(f"results cards: {rc} | bios: {bc}")
    snap = snapshot.save_all()
    print(f"snapshot saved: {json.dumps(snap)}")


if __name__ == "__main__":
    main()
