from __future__ import annotations

import sqlite3
from pathlib import Path
from src.storage.models import Opportunity
from src.utils.time_utils import utc_now_iso

SCHEMA = """
CREATE TABLE IF NOT EXISTS opportunities (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  url TEXT,
  source_name TEXT NOT NULL,
  source_url TEXT NOT NULL,
  publish_date TEXT,
  deadline TEXT,
  event_date TEXT,
  location TEXT,
  summary TEXT,
  raw_text TEXT,
  score INTEGER,
  category TEXT,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  UNIQUE(url),
  UNIQUE(title, source_name)
);
"""


def connect(db_path: str = "data/opportunities.sqlite3") -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(SCHEMA)
    return conn


def upsert_opportunity(conn: sqlite3.Connection, opp: Opportunity) -> bool:
    now = utc_now_iso()
    key_clause, params = ("url = ?", (opp.url,)) if opp.url else ("title = ? AND source_name = ?", (opp.title, opp.source_name))
    row = conn.execute(f"SELECT id, first_seen_at FROM opportunities WHERE {key_clause}", params).fetchone()
    if row:
        conn.execute(
            """UPDATE opportunities SET publish_date=?, deadline=?, event_date=?, location=?, summary=?, raw_text=?, score=?, category=?, last_seen_at=? WHERE id=?""",
            (opp.publish_date, opp.deadline, opp.event_date, opp.location, opp.summary, opp.raw_text, opp.score, opp.category, now, row["id"]),
        )
        return False
    conn.execute(
        """INSERT INTO opportunities (title, url, source_name, source_url, publish_date, deadline, event_date, location, summary, raw_text, score, category, first_seen_at, last_seen_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (opp.title, opp.url, opp.source_name, opp.source_url, opp.publish_date, opp.deadline, opp.event_date, opp.location, opp.summary, opp.raw_text, opp.score, opp.category, now, now),
    )
    return True


def list_by_last_seen(conn: sqlite3.Connection, day_prefix: str) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM opportunities WHERE last_seen_at LIKE ? ORDER BY category, score DESC", (f"{day_prefix}%",)).fetchall()
