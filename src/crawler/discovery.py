from __future__ import annotations

from dataclasses import dataclass

from src.crawler.content import compact_summary, content_hash, extract_document
from src.crawler.feeds import discover_feed_urls, parse_feed
from src.crawler.fetch_static import fetch_url
from src.crawler.parse_page import parse_items
from src.storage.models import InformationItem


@dataclass
class CrawlResult:
    items: list[InformationItem]
    status: str
    message: str = ""
    mode: str = "html"


def _looks_like_feed(url: str, body: str) -> bool:
    prefix = body.lstrip()[:200].lower()
    return (
        url.lower().endswith((".xml", ".rss", ".atom"))
        or "<rss" in prefix
        or "<feed" in prefix
    )


def _hydrate_details(items: list[InformationItem], source: dict) -> list[InformationItem]:
    if source.get("fetch_details", True) is False:
        for item in items:
            base = item.raw_text or item.summary
            item.content = base
            item.content_hash = content_hash(base)
        return items

    limit = max(1, int(source.get("max_detail_items", source.get("max_items", 30))))
    for item in items[:limit]:
        if not item.url:
            continue
        html = fetch_url(item.url, timeout=int(source.get("detail_timeout", 15)))
        if not html:
            base = item.raw_text or item.summary
            item.content = base
            item.content_hash = content_hash(base)
            continue

        document = extract_document(html)
        text = document["text"]
        if text:
            item.content = text
            item.raw_text = text
            item.summary = compact_summary(text)
            item.content_hash = content_hash(text)
            detail_title = document.get("title") or ""
            if len(item.title) < 6 and detail_title:
                item.title = detail_title
        else:
            base = item.raw_text or item.summary
            item.content = base
            item.content_hash = content_hash(base)

    return items


def crawl_source(source: dict) -> CrawlResult:
    """Crawl one source, preferring RSS/Atom and falling back to HTML discovery."""
    body = fetch_url(source["url"], timeout=int(source.get("timeout", 20)))
    if not body:
        return CrawlResult([], "error", "source_fetch_failed")

    items: list[InformationItem] = []
    mode = "html"

    if _looks_like_feed(source["url"], body):
        items = parse_feed(body, source)
        mode = "feed"
    else:
        for feed_url in discover_feed_urls(body, source["url"]):
            feed_body = fetch_url(feed_url, timeout=int(source.get("timeout", 20)))
            if not feed_body:
                continue
            feed_items = parse_feed(feed_body, source)
            if feed_items:
                items = feed_items
                mode = "feed"
                break

    if not items:
        items = parse_items(body, source)
        mode = "html"

    items = _hydrate_details(items, source)
    return CrawlResult(items, "ok", f"{len(items)} items via {mode}", mode=mode)
