from __future__ import annotations

from datetime import date, datetime, timezone
import re


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def today_date() -> date:
    return date.today()


def parse_date(text: str | None) -> str | None:
    if not text:
        return None
    patterns = [
        r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})日?",
        r"(\d{1,2})[-/.月](\d{1,2})日?",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if not m:
            continue
        try:
            if len(m.groups()) == 3:
                y, mo, d = map(int, m.groups())
            else:
                y = today_date().year
                mo, d = map(int, m.groups())
            return date(y, mo, d).isoformat()
        except ValueError:
            continue
    return None


def is_before_today(iso_date: str | None) -> bool:
    if not iso_date:
        return False
    try:
        return date.fromisoformat(iso_date) < today_date()
    except ValueError:
        return False
