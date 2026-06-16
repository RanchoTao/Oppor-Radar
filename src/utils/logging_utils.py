from __future__ import annotations

import logging
import os


def setup_logging() -> None:
    level = os.getenv("OPPORTUNITY_RADAR_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
