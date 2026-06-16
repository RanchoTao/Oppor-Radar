from __future__ import annotations

import logging
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

LOGGER = logging.getLogger(__name__)


def fetch_url(url: str, timeout: int = 15) -> str | None:
    try:
        import requests
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "OpportunityRadar/0.1"})
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or resp.encoding
        return resp.text
    except ModuleNotFoundError:
        return _fetch_with_urllib(url, timeout)
    except Exception as exc:
        LOGGER.warning("Failed to fetch %s: %s", url, exc)
        return None


def _fetch_with_urllib(url: str, timeout: int) -> str | None:
    req = Request(url, headers={"User-Agent": "OpportunityRadar/0.1"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            content = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return content.decode(charset, errors="replace")
    except (URLError, HTTPError, TimeoutError) as exc:
        LOGGER.warning("Failed to fetch %s: %s", url, exc)
        return None
