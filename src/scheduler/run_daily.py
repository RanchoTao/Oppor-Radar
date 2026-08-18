from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

try:
    import yaml
except ModuleNotFoundError:
    from src.utils import simple_yaml as yaml

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*args, **kwargs):
        return False

from src.crawler.discovery import crawl_source
from src.extractor.rules import enrich_with_rules
from src.llm.deepseek_digest import build_daily_digest, rank_items
from src.notifier.markdown_report import generate_report
from src.storage.db import (
    connect,
    list_changed_on,
    list_source_health,
    update_item_intelligence,
    update_source_health,
    upsert_item,
)
from src.utils.logging_utils import setup_logging

LOGGER = logging.getLogger(__name__)


def load_yaml(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f.read())


def _today(profile: dict) -> str:
    timezone_name = profile.get("timezone", "Asia/Shanghai")
    try:
        return datetime.now(ZoneInfo(timezone_name)).date().isoformat()
    except Exception:
        return datetime.now(timezone.utc).date().isoformat()


def _apply_intelligence(conn, rows, results: list[dict]) -> None:
    by_url = {str(result.get("url")): result for result in results if result.get("url")}
    by_identity = {
        (str(result.get("source")), str(result.get("title"))): result
        for result in results
        if result.get("source") and result.get("title")
    }
    for row in rows:
        result = None
        if row["url"]:
            result = by_url.get(str(row["url"]))
        if result is None:
            result = by_identity.get((str(row["source_name"]), str(row["title"])))
        if result is None:
            continue
        update_item_intelligence(
            conn,
            row["url"],
            row["source_name"],
            row["title"],
            result,
        )


def main() -> None:
    load_dotenv()
    setup_logging()

    sources = load_yaml("config/sources.yaml") or []
    profile = load_yaml("config/profile.yaml") or {}
    sources = [source for source in sources if source.get("enabled", True)]

    conn = connect(os.getenv("OPPORTUNITY_RADAR_DB", "data/opportunities.sqlite3"))
    new_count = 0
    changed_count = 0
    unchanged_count = 0
    failed = 0

    for source in sources:
        LOGGER.info("Crawling source: %s [%s]", source["name"], source.get("group", "未分组"))
        result = crawl_source(source)
        if result.status != "ok":
            failed += 1
            update_source_health(conn, source, "error", result.message, 0)
            conn.commit()
            continue

        for item in result.items:
            item = enrich_with_rules(item)
            status = upsert_item(conn, item)
            if status == "new":
                new_count += 1
            elif status == "changed":
                changed_count += 1
            else:
                unchanged_count += 1

        update_source_health(
            conn,
            source,
            "healthy",
            f"{result.mode}: {len(result.items)} discovered",
            len(result.items),
        )
        conn.commit()

    report_date = _today(profile)
    # Database timestamps are UTC. Keeping selection anchored to UTC avoids losing
    # items when a manual run occurs just after local midnight in Asia/Shanghai.
    storage_day = datetime.now(timezone.utc).date().isoformat()
    candidate_rows = list_changed_on(conn, storage_day, kept_only=False)
    item_results, item_llm = rank_items(candidate_rows, sources, profile)
    _apply_intelligence(conn, candidate_rows, item_results)
    conn.commit()

    selected_rows = list_changed_on(conn, storage_day, kept_only=True)
    digest = build_daily_digest(selected_rows, sources, report_date, profile)
    health_rows = list_source_health(conn)
    healthy = sum(1 for row in health_rows if row["status"] == "healthy")

    timezone_name = profile.get("timezone", "Asia/Shanghai")
    source_stats = {
        "configured": len(sources),
        "healthy": healthy,
        "failed": failed,
        "new_items": new_count,
        "changed_items": changed_count,
        "unchanged_items": unchanged_count,
        "candidate_items": len(candidate_rows),
        "selected_items": len(selected_rows),
        "item_intelligence": item_llm,
        "last_updated_at": datetime.now(ZoneInfo(timezone_name)).isoformat(),
        "source_health": [dict(row) for row in health_rows],
    }

    report = generate_report(
        selected_rows,
        report_date,
        os.getenv("OPPORTUNITY_RADAR_REPORT_DIR", "data/reports"),
        digest=digest,
        source_stats=source_stats,
    )

    LOGGER.info(
        "Daily intelligence finished: new=%s changed=%s selected=%s sources=%s/%s report=%s",
        new_count,
        changed_count,
        len(selected_rows),
        healthy,
        len(sources),
        report,
    )


if __name__ == "__main__":
    main()
