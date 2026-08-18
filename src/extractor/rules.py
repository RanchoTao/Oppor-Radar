from __future__ import annotations

import re

from src.storage.models import InformationItem
from src.utils.time_utils import parse_date


def enrich_with_rules(item: InformationItem) -> InformationItem:
    """Extract optional structured metadata without imposing an application taxonomy."""
    text = f"{item.title} {item.summary} {item.raw_text}"

    deadline = _date_after(text, ["截止", "报名", "申请", "deadline", "due"])
    event_date = _date_after(text, ["时间", "活动", "讲座", "会议", "event", "date"])
    publish_date = _date_after(text, ["发布", "日期", "published", "updated"])

    if deadline:
        item.deadline = deadline
    if event_date:
        item.event_date = event_date
    if publish_date and not item.publish_date:
        item.publish_date = publish_date

    loc = re.search(r"(?:地点|地址|位置|location)[:：]?\s*([^，。；;\n]{2,60})", text, re.IGNORECASE)
    if loc and not item.location:
        item.location = loc.group(1).strip()
    return item


def _date_after(text: str, markers: list[str]) -> str | None:
    lower = text.lower()
    for marker in markers:
        idx = lower.find(marker.lower())
        if idx >= 0:
            parsed = parse_date(text[idx : idx + 100])
            if parsed:
                return parsed
    return None
