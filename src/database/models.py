import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS companies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    code            TEXT    NOT NULL UNIQUE,
    name            TEXT    NOT NULL,
    name_en         TEXT,
    sector          TEXT,
    keywords        TEXT,
    enabled         INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS market_data (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT    NOT NULL,
    company_code    TEXT,
    data_type       TEXT    NOT NULL,
    open_price      REAL,
    high_price      REAL,
    low_price       REAL,
    close_price     REAL,
    volume          INTEGER,
    turnover        REAL,
    change_amount   REAL,
    change_pct      REAL,
    advance_count   INTEGER,
    decline_count   INTEGER,
    unchanged_count INTEGER,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE(date, company_code, data_type)
);

CREATE TABLE IF NOT EXISTS news (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT    NOT NULL,
    company_code    TEXT,
    source          TEXT    NOT NULL,
    title           TEXT    NOT NULL,
    url             TEXT,
    summary         TEXT,
    published_at    TEXT,
    sentiment       TEXT,
    relevance_score REAL,
    used_in_episode INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE(url)
);

CREATE TABLE IF NOT EXISTS analysis (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT    NOT NULL UNIQUE,
    market_summary  TEXT,
    spotlight_companies TEXT,
    theme_analysis  TEXT,
    tomorrow_points TEXT,
    trending_stocks TEXT,
    volume_stocks   TEXT,
    trending_themes TEXT,
    keywords        TEXT,
    raw_prompt      TEXT,
    model_used      TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS episodes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT    NOT NULL UNIQUE,
    title           TEXT    NOT NULL,
    script_path     TEXT,
    audio_path      TEXT,
    duration_seconds INTEGER,
    file_size_bytes INTEGER,
    rss_published   INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_market_data_date ON market_data(date);
CREATE INDEX IF NOT EXISTS idx_news_date ON news(date);
CREATE INDEX IF NOT EXISTS idx_news_company ON news(company_code);
CREATE INDEX IF NOT EXISTS idx_episodes_date ON episodes(date);
"""


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database(db_path: str) -> None:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)
    logger.info(f"データベース初期化完了: {db_path}")
