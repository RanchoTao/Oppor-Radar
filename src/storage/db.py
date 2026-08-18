from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.storage.models import InformationItem
from src.utils.time_utils import utc_now_iso

ITEM_SCHEMA = """
CREATE TABLE IF NOT EXISTS information_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  url TEXT,
  source_name TEXT NOT NULL,
  source_url TEXT NOT NULL,
  source_group TEXT NOT NULL DEFAULT '未分组',
  publish_date TEXT,
  deadline TEXT,
  event_date TEXT,
  location TEXT,
  summary TEXT NOT NULL DEFAULT '',
  content TEXT NOT NULL DEFAULT '',
  raw_text TEXT NOT NULL DEFAULT '',
  content_hash TEXT NOT NULL DEFAULT '',
  topics_json TEXT NOT NULL DEFAULT '[]',
  importance REAL NOT NULL DEFAULT 0,
  relevance REAL NOT NULL DEFAULT 0,
  novelty REAL NOT NULL DEFAULT 0,
  keep INTEGER NOT NULL DEFAULT 1,
  reason TEXT NOT NULL DEFAULT '',
  action TEXT NOT NULL DEFAULT '',
  time_sensitive INTEGER NOT NULL DEFAULT 0,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  changed_at TEXT NOT NULL,
  UNIQUE(url),
  UNIQUE(title, source_name)
);
"""

HEALTH_SCHEMA = """
CREATE TABLE IF NOT EXISTS source_health (
  source_name TEXT PRIMARY KEY,
  source_url TEXT NOT NULL,
  source_group TEXT NOT NULL DEFAULT '未分组',
  status TEXT NOT NULL,
  message TEXT NOT NULL DEFAULT '',
  discovered_items INTEGER NOT NULL DEFAULT 0,
  checked_at TEXT NOT NULL
);
"""


def connect(db_path: str = "data/opportunities.sqlite3") -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(ITEM_SCHEMA)
    conn.execute(HEALTH_SCHEMA)
    _migrate_legacy_opportunities(conn)
    conn.commit()
    return conn


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _migrate_legacy_opportunities(conn: sqlite3.Connection) -> None:
    """Copy old application-centric rows once, without keeping old ranking semantics."""
    if not _table_exists(conn, "opportunities"):
        return
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(opportunities)")}
    required = {"title", "source_name", "source_url", "first_seen_at", "last_seen_at"}
    if not required.issubset(columns):
        return

    rows = conn.execute("SELECT * FROM opportunities").fetchall()
    for row in rows:
        now = row["last_seen_at"] or row["first_seen_at"] or utc_now_iso()
        conn.execute(
            """
            INSERT OR IGNORE INTO information_items (
              title, url, source_name, source_url, source_group,
              publish_date, deadline, event_date, location,
              summary, content, raw_text, content_hash,
              first_seen_at, last_seen_at, changed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["title"],
                row["url"] if "url" in columns else None,
                row["source_name"],
                row["source_url"],
                "学术",
                row["publish_date"] if "publish_date" in columns else None,
                row["deadline"] if "deadline" in columns else None,
                row["event_date"] if "event_date" in columns else None,
                row["location"] if "location" in columns else None,
                row["summary"] if "summary" in columns else "",
                row["raw_text"] if "raw_text" in columns else "",
                row["raw_text"] if "raw_text" in columns else "",
                "",
                row["first_seen_at"],
                row["last_seen_at"],
                now,
            ),
        )


def _key(item: InformationItem) -> tuple[str, tuple]:
    if item.url:
        return "url = ?", (item.url,)
    return "title = ? AND source_name = ?", (item.title, item.source_name)


def upsert_item(conn: sqlite3.Connection, item: InformationItem) -> str:
    """Return one of: new, changed, unchanged."""
    now = utc_now_iso()
    key_clause, params = _key(item)
    row = conn.execute(
        f"SELECT id, content_hash FROM information_items WHERE {key_clause}", params
    ).fetchone()

    if row is None:
        conn.execute(
            """
            INSERT INTO information_items (
              title, url, source_name, source_url, source_group,
              publish_date, deadline, event_date, location,
              summary, content, raw_text, content_hash,
              first_seen_at, last_seen_at, changed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.title,
                item.url,
                item.source_name,
                item.source_url,
                item.group,
                item.publish_date,
                item.deadline,
                item.event_date,
                item.location,
                item.summary,
                item.content,
                item.raw_text,
                item.content_hash,
                now,
                now,
                now,
            ),
        )
        return "new"

    old_hash = row["content_hash"] or ""
    changed = bool(item.content_hash and item.content_hash != old_hash)
    conn.execute(
        """
        UPDATE information_items SET
          title=?, source_url=?, source_group=?, publish_date=?, deadline=?,
          event_date=?, location=?, summary=?, content=?, raw_text=?, content_hash=?,
          last_seen_at=?, changed_at=CASE WHEN ? THEN ? ELSE changed_at END
        WHERE id=?
        """,
        (
            item.title,
            item.source_url,
            item.group,
            item.publish_date,
            item.deadline,
            item.event_date,
            item.location,
            item.summary,
            item.content,
            item.raw_text,
            item.content_hash or old_hash,
            now,
            1 if changed else 0,
            now,
            row["id"],
        ),
    )
    return "changed" if changed else "unchanged"


def update_item_intelligence(conn: sqlite3.Connection, key_url: str | None, source_name: str, title: str, result: dict) -> None:
    key_clause, params = (
        ("url = ?", (key_url,))
        if key_url
        else ("title = ? AND source_name = ?", (title, source_name))
    )
    conn.execute(
        f"""
        UPDATE information_items SET
          summary=?, topics_json=?, importance=?, relevance=?, novelty=?, keep=?,
          reason=?, action=?, time_sensitive=?
        WHERE {key_clause}
        """,
        (
            str(result.get("summary") or "")[:2000],
            json.dumps(result.get("topics") or [], ensure_ascii=False),
            float(result.get("importance") or 0),
            float(result.get("relevance") or 0),
            float(result.get("novelty") or 0),
            1 if result.get("keep", True) else 0,
            str(result.get("reason") or "")[:1000],
            str(result.get("action") or "")[:1000],
            1 if result.get("time_sensitive", False) else 0,
            *params,
        ),
    )


def list_changed_since(conn: sqlite3.Connection, timestamp: str, kept_only: bool = False) -> list[sqlite3.Row]:
    """Return only information first seen or materially changed during this run."""
    where_keep = " AND keep = 1" if kept_only else ""
    return conn.execute(
        f"""
        SELECT * FROM information_items
        WHERE changed_at >= ?{where_keep}
        ORDER BY relevance DESC, importance DESC, novelty DESC, changed_at DESC
        """,
        (timestamp,),
    ).fetchall()


def list_changed_on(conn: sqlite3.Connection, day_prefix: str, kept_only: bool = False) -> list[sqlite3.Row]:
    where_keep = " AND keep = 1" if kept_only else ""
    return conn.execute(
        f"""
        SELECT * FROM information_items
        WHERE (first_seen_at LIKE ? OR changed_at LIKE ?){where_keep}
        ORDER BY relevance DESC, importance DESC, novelty DESC, changed_at DESC
        """,
        (f"{day_prefix}%", f"{day_prefix}%"),
    ).fetchall()


def list_by_first_seen(conn: sqlite3.Connection, day_prefix: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM information_items WHERE first_seen_at LIKE ? ORDER BY first_seen_at DESC",
        (f"{day_prefix}%",),
    ).fetchall()


def list_by_last_seen(conn: sqlite3.Connection, day_prefix: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM information_items WHERE last_seen_at LIKE ? ORDER BY last_seen_at DESC",
        (f"{day_prefix}%",),
    ).fetchall()


def update_source_health(
    conn: sqlite3.Connection,
    source: dict,
    status: str,
    message: str = "",
    discovered_items: int = 0,
) -> None:
    conn.execute(
        """
        INSERT INTO source_health (
          source_name, source_url, source_group, status, message, discovered_items, checked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_name) DO UPDATE SET
          source_url=excluded.source_url,
          source_group=excluded.source_group,
          status=excluded.status,
          message=excluded.message,
          discovered_items=excluded.discovered_items,
          checked_at=excluded.checked_at
        """,
        (
            source["name"],
            source["url"],
            source.get("group", "未分组"),
            status,
            message[:500],
            discovered_items,
            utc_now_iso(),
        ),
    )


def list_source_health(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM source_health ORDER BY source_group, source_name"
    ).fetchall()


# Compatibility for legacy tests/imports. New code uses upsert_item.
def upsert_opportunity(conn: sqlite3.Connection, item: InformationItem) -> bool:
    return upsert_item(conn, item) == "new"
