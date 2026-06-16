from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Opportunity:
    title: str
    url: str | None
    source_name: str
    source_url: str
    publish_date: str | None = None
    deadline: str | None = None
    event_date: str | None = None
    location: str | None = None
    summary: str = ""
    raw_text: str = ""
    score: int = 0
    category: str = "X"
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    reason: str = ""
