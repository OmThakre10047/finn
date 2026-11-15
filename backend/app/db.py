import sqlite3
from contextlib import contextmanager

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS portfolio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT UNIQUE NOT NULL,
    exchange TEXT DEFAULT 'NSE',
    name TEXT,
    is_active INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS watch_types (
    key TEXT PRIMARY KEY,
    label TEXT,
    is_enabled INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS alert_settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    volume_mult REAL DEFAULT 2.0,
    price_move_pct REAL DEFAULT 4.0,
    window_hours INTEGER DEFAULT 24
);
CREATE TABLE IF NOT EXISTS announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    headline TEXT,
    nse_category TEXT,
    subject TEXT,
    category TEXT,
    materiality TEXT,
    priority REAL DEFAULT 0,
    pdf_url TEXT,
    published_at TEXT,
    raw_json TEXT,
    summary TEXT,
    rules_handled INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(ticker, headline, published_at)
);
CREATE INDEX IF NOT EXISTS idx_ann_pub ON announcements(published_at);
CREATE INDEX IF NOT EXISTS idx_ann_ticker ON announcements(ticker);
CREATE TABLE IF NOT EXISTS renders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    announcement_id INTEGER NOT NULL REFERENCES announcements(id),
    kind TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(announcement_id, kind)
);
CREATE TABLE IF NOT EXISTS price_bars (
    ticker TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL,
    volume INTEGER,
    fetched_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (ticker, date)
);
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    type TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    severity TEXT DEFAULT 'info',
    dedupe_key TEXT UNIQUE,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS filings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    kind TEXT NOT NULL,
    url TEXT,
    period TEXT,
    path TEXT,
    content_hash TEXT,
    fetched_at TEXT DEFAULT (datetime('now')),
    UNIQUE(ticker, kind, url)
);
CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filing_id INTEGER NOT NULL REFERENCES filings(id),
    idx INTEGER NOT NULL,
    text TEXT NOT NULL,
    page INTEGER
);
CREATE TABLE IF NOT EXISTS research_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT UNIQUE NOT NULL,
    status TEXT DEFAULT 'pending',
    payload_json TEXT,
    generated_at TEXT,
    expires_at TEXT
);
CREATE TABLE IF NOT EXISTS llm_cache (
    key_hash TEXT PRIMARY KEY,
    model TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    hits INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS llm_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    cache_hit INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS source_state (
    source TEXT PRIMARY KEY,
    mode TEXT DEFAULT 'never',
    last_ok_at TEXT,
    last_error TEXT
);
CREATE TABLE IF NOT EXISTS kv (
    k TEXT PRIMARY KEY,
    v TEXT
);
"""


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as db:
        db.executescript(SCHEMA)
        try:
            db.execute("ALTER TABLE alerts ADD COLUMN dedupe_key TEXT")
        except sqlite3.OperationalError:
            pass
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_alerts_dedupe ON alerts(dedupe_key) WHERE dedupe_key IS NOT NULL")
        migrate_published_at(db)


def migrate_published_at(db: sqlite3.Connection) -> None:
    """Normalise legacy NSE 'dd-Mon-yyyy HH:MM:SS' published_at to ISO."""
    from .nse_client import iso_pub

    rows = db.execute(
        "SELECT id, published_at FROM announcements WHERE published_at IS NOT NULL AND published_at NOT GLOB '[0-9][0-9][0-9][0-9]-*'"
    ).fetchall()
    for r in rows:
        iso = iso_pub(r["published_at"])
        if iso:
            db.execute("UPDATE announcements SET published_at = ? WHERE id = ?", (iso, r["id"]))


def get_source_state(source: str):
    with get_db() as db:
        row = db.execute("SELECT * FROM source_state WHERE source = ?", (source,)).fetchone()
        return dict(row) if row else {"source": source, "mode": "never", "last_ok_at": None, "last_error": None}


def set_source_state(source: str, mode: str, error: str | None = None) -> None:
    with get_db() as db:
        db.execute(
            """INSERT INTO source_state (source, mode, last_ok_at, last_error)
               VALUES (?, ?, CASE WHEN ? = 'live' THEN datetime('now') ELSE NULL END, ?)
               ON CONFLICT(source) DO UPDATE SET
                 mode = excluded.mode,
                 last_ok_at = CASE WHEN excluded.mode = 'live' THEN datetime('now') ELSE source_state.last_ok_at END,
                 last_error = excluded.last_error""",
            (source, mode, mode, error),
        )


def kv_get(k: str) -> str | None:
    with get_db() as db:
        row = db.execute("SELECT v FROM kv WHERE k = ?", (k,)).fetchone()
        return row["v"] if row else None


def kv_set(k: str, v: str) -> None:
    with get_db() as db:
        db.execute("INSERT OR REPLACE INTO kv (k, v) VALUES (?, ?)", (k, v))
