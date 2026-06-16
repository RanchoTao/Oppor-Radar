from __future__ import annotations

import re
from urllib.parse import urljoin, urlsplit, urlunsplit, urldefrag


def clean_text(text: str | None) -> str:
    text = text or ""
    return re.sub(r"\s+", " ", text).strip()


def normalize_url(url: str | None, base_url: str | None = None) -> str | None:
    if not url:
        return None
    absolute = urljoin(base_url or "", url.strip())
    absolute, _ = urldefrag(absolute)
    parts = urlsplit(absolute)
    if not parts.scheme or not parts.netloc:
        return None
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((scheme, netloc, path, parts.query, ""))


def contains_any(text: str, keywords: list[str]) -> bool:
    lower = text.lower()
    return any(k.lower() in lower for k in keywords)
