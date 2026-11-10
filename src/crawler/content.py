from __future__ import annotations

import hashlib
import re
from html import unescape

from src.utils.text_utils import clean_text


NOISE_TAGS = ["script", "style", "noscript", "nav", "footer", "header", "form", "aside"]


def content_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", (text or "")).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest() if normalized else ""


def text_similarity(a: str, b: str, n: int = 6, limit: int = 12000) -> float:
    """Jaccard similarity of character n-gram sets, robust to CJK text without spaces.

    Used to decide whether a page *materially* changed: rotating "related posts",
    view counters or relative dates move the hash but keep similarity high.
    """
    def grams(text: str) -> set[str]:
        compact = re.sub(r"\s+", "", (text or "").lower())[:limit]
        if len(compact) <= n:
            return {compact} if compact else set()
        return {compact[i : i + n] for i in range(len(compact) - n + 1)}

    left, right = grams(a), grams(b)
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def extract_document(html: str) -> dict[str, str]:
    """Extract a readable title and main-text approximation from an HTML detail page."""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        for tag_name in NOISE_TAGS:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        title = ""
        if soup.title and soup.title.string:
            title = clean_text(soup.title.string)

        root = soup.find("article") or soup.find("main") or soup.body or soup
        text = clean_text(root.get_text(" ", strip=True))
        return {"title": title, "text": text[:24000]}
    except ModuleNotFoundError:
        text = re.sub(r"<[^>]+>", " ", html)
        return {"title": "", "text": clean_text(unescape(text))[:24000]}


def compact_summary(text: str, limit: int = 1200) -> str:
    text = clean_text(text)
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"
