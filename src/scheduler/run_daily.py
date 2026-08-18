from __future__ import annotations

import logging
import os
from datetime import date
from pathlib import Path

try:
    import yaml
except ModuleNotFoundError:
    from src.utils import simple_yaml as yaml

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*args, **kwargs):
        return False

from src.crawler.fetch_static import fetch_url
from src.crawler.parse_page import parse_opportunities
from src.extractor.rules import enrich_with_rules
from src.llm.deepseek_digest import build_daily_digest
from src.notifier.markdown_report import generate_report
from src.storage.db import connect, list_by_first_seen, upsert_opportunity
from src.utils.logging_utils import setup_logging

LOGGER = logging.getLogger(__name__)


def load_yaml(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f.read())


def main() -> None:
    load_dotenv()
    setup_logging()
    sources = load_yaml("config/sources.yaml") or []
    keywords = load_yaml("config/keywords.yaml") or {}
    conn = connect(os.getenv("OPPORTUNITY_RADAR_DB", "data/opportunities.sqlite3"))

    new_count = 0
    scanned = 0
    failed = 0
    source_new_counts: dict[str, int] = {}

    for source in sources:
        LOGGER.info("Fetching source: %s [%s]", source["name"], source.get("group", "未分组"))
        html = fetch_url(source["url"])
        if not html:
            failed += 1
            source_new_counts[source["name"]] = 0
            continue

        scanned += 1
        Path("data/snapshots").mkdir(parents=True, exist_ok=True)
        safe_name = "".join(c if c.isalnum() else "_" for c in source["name"])
        Path(f"data/snapshots/{safe_name}.html").write_text(html, encoding="utf-8")

        source_new = 0
        for item in parse_opportunities(html, source, keywords):
            item = enrich_with_rules(item)
            if upsert_opportunity(conn, item):
                new_count += 1
                source_new += 1
        source_new_counts[source["name"]] = source_new
        conn.commit()

    today = date.today().isoformat()
    rows = list_by_first_seen(conn, today)
    digest = build_daily_digest(rows, sources, today)
    source_stats = {
        "configured": len(sources),
        "scanned": scanned,
        "failed": failed,
        "new_items": new_count,
        "by_source": source_new_counts,
    }
    report = generate_report(
        rows,
        today,
        os.getenv("OPPORTUNITY_RADAR_REPORT_DIR", "data/reports"),
        digest=digest,
        source_stats=source_stats,
    )
    LOGGER.info(
        "Daily job finished: %s new items, %s/%s sources scanned, llm=%s, report=%s",
        new_count,
        scanned,
        len(sources),
        (digest.get("llm") or {}).get("used"),
        report,
    )


if __name__ == "__main__":
    main()
