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
from src.extractor.llm_stub import enrich_with_llm_stub
from src.notifier.markdown_report import generate_report
from src.scorer.score import score_opportunity
from src.storage.db import connect, upsert_opportunity, list_by_last_seen
from src.utils.logging_utils import setup_logging

LOGGER = logging.getLogger(__name__)


def load_yaml(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f.read())


def main() -> None:
    load_dotenv()
    setup_logging()
    sources = load_yaml("config/sources.yaml")
    keywords = load_yaml("config/keywords.yaml")
    scoring = load_yaml("config/scoring.yaml")
    conn = connect(os.getenv("OPPORTUNITY_RADAR_DB", "data/opportunities.sqlite3"))
    new_count = 0
    for source in sources:
        LOGGER.info("Fetching source: %s", source["name"])
        html = fetch_url(source["url"])
        if not html:
            continue
        Path("data/snapshots").mkdir(parents=True, exist_ok=True)
        safe_name = ''.join(c if c.isalnum() else '_' for c in source['name'])
        Path(f"data/snapshots/{safe_name}.html").write_text(html, encoding="utf-8")
        for opp in parse_opportunities(html, source, keywords):
            opp = enrich_with_llm_stub(enrich_with_rules(opp))
            opp = score_opportunity(opp, keywords, scoring)
            if upsert_opportunity(conn, opp):
                new_count += 1
        conn.commit()
    today = date.today().isoformat()
    rows = list_by_last_seen(conn, today)
    report = generate_report(rows, today, os.getenv("OPPORTUNITY_RADAR_REPORT_DIR", "data/reports"))
    LOGGER.info("Daily job finished: %s new opportunities, report=%s", new_count, report)


if __name__ == "__main__":
    main()
