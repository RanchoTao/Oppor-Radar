from __future__ import annotations

import re
from src.storage.models import Opportunity
from src.utils.time_utils import parse_date


def enrich_with_rules(opp: Opportunity) -> Opportunity:
    text = f"{opp.title} {opp.summary} {opp.raw_text}"
    opp.deadline = _date_after(text, ["截止", "报名", "申请"])
    opp.event_date = _date_after(text, ["时间", "活动", "讲座", "开营"])
    opp.publish_date = _date_after(text, ["发布", "日期"])
    loc = re.search(r"(?:地点|地址|位置)[:：]?\s*([^，。；;\n]{2,40})", text)
    if loc:
        opp.location = loc.group(1).strip()
    return opp


def _date_after(text: str, markers: list[str]) -> str | None:
    for marker in markers:
        idx = text.find(marker)
        if idx >= 0:
            parsed = parse_date(text[idx: idx + 80])
            if parsed:
                return parsed
    return None
