"""Opslag: één sqlite-bestand met artikelen en edities."""
import json
import sqlite3
from datetime import datetime, timedelta, timezone

from .config import DATA_DIR

DB_PATH = DATA_DIR / "krant.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    url        TEXT PRIMARY KEY,
    source     TEXT NOT NULL,
    section    TEXT NOT NULL,
    title      TEXT NOT NULL,
    summary    TEXT,
    html       TEXT,
    image      TEXT,
    published  TEXT,
    fetched    TEXT NOT NULL,
    words      INTEGER DEFAULT 0,
    status     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_articles_pub ON articles(published DESC);

CREATE TABLE IF NOT EXISTS editions (
    day        TEXT PRIMARY KEY,
    created    TEXT NOT NULL,
    payload    TEXT NOT NULL
);
"""


def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init():
    with connect() as con:
        con.executescript(SCHEMA)


def known_urls():
    with connect() as con:
        return {r[0] for r in con.execute("SELECT url FROM articles")}


def save_article(a):
    with connect() as con:
        con.execute(
            """INSERT INTO articles (url, source, section, title, summary, html, image,
                                     published, fetched, words, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(url) DO UPDATE SET
                 title=excluded.title, summary=excluded.summary,
                 html=CASE WHEN excluded.html IS NOT NULL AND length(excluded.html) > 0
                           THEN excluded.html ELSE articles.html END,
                 image=COALESCE(excluded.image, articles.image),
                 words=MAX(excluded.words, articles.words),
                 status=CASE WHEN excluded.status='full' THEN 'full' ELSE articles.status END""",
            (a["url"], a["source"], a["section"], a["title"], a.get("summary"), a.get("html"),
             a.get("image"), a.get("published"), a.get("fetched"), a.get("words", 0), a["status"]),
        )


def candidates(hours):
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with connect() as con:
        rows = con.execute("SELECT * FROM articles WHERE published >= ?", (cutoff,)).fetchall()
    return [dict(r) for r in rows]


def save_edition(day, payload):
    with connect() as con:
        con.execute(
            "INSERT INTO editions (day, created, payload) VALUES (?,?,?) "
            "ON CONFLICT(day) DO UPDATE SET created=excluded.created, payload=excluded.payload",
            (day, datetime.now(timezone.utc).isoformat(), json.dumps(payload)),
        )


def get_edition(day=None):
    with connect() as con:
        if day:
            row = con.execute("SELECT * FROM editions WHERE day=?", (day,)).fetchone()
        else:
            row = con.execute("SELECT * FROM editions ORDER BY day DESC LIMIT 1").fetchone()
    if not row:
        return None
    return {"day": row["day"], "created": row["created"], "payload": json.loads(row["payload"])}


def all_editions(limit=30):
    with connect() as con:
        rows = con.execute("SELECT day, created FROM editions ORDER BY day DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def count_articles():
    with connect() as con:
        return con.execute("SELECT COUNT(*) FROM articles").fetchone()[0]