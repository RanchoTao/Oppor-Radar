from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from urllib.parse import urlparse

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


def _fallback_content(item: InformationItem) -> None:
    base = item.raw_text or item.summary or item.title
    item.content = base
    item.content_hash = content_hash(base)


def _should_fetch_detail(item: InformationItem, source: dict) -> bool:
    if not item.url:
        return False
    if source.get("fetch_details", True) is False:
        return False

    path = urlparse(item.url).path.lower()
    if path.endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar")):
        return False

    if source.get("fetch_external_details", False):
        return True

    source_host = (urlparse(source["url"]).hostname or "").lower()
    item_host = (urlparse(item.url).hostname or "").lower()
    return bool(source_host and item_host and source_host == item_host)


def _hydrate_one(item: InformationItem, source: dict) -> InformationItem:
    html = fetch_url(item.url, timeout=int(source.get("detail_timeout", 8))) if item.url else None
    if not html:
        _fallback_content(item)
        return item

    document = extract_document(html)
    text = document["text"]
    if not text:
        _fallback_content(item)
        return item

    item.content = text
    item.raw_text = text
    item.summary = compact_summary(text)
    item.content_hash = content_hash(text)
    detail_title = document.get("title") or ""
    if len(item.title) < 6 and detail_title:
        item.title = detail_title
    return item


def _hydrate_details(items: list[InformationItem], source: dict) -> list[InformationItem]:
    """Hydrate a bounded number of detail pages without serializing network latency."""
    limit = max(0, int(source.get("max_detail_items", source.get("max_items", 30))))
    eligible = [item for item in items if _should_fetch_detail(item, source)][:limit]
    eligible_ids = {id(item) for item in eligible}

    # Every item needs a stable fingerprint even if it is not worth a detail request.
    for item in items:
        if id(item) not in eligible_ids:
            _fallback_content(item)

    if not eligible:
        return items

    workers = max(1, min(int(source.get("detail_workers", 4)), len(eligible), 8))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="oppor-detail") as pool:
        futures = {pool.submit(_hydrate_one, item, source): item for item in eligible}
        for future in as_completed(futures):
            item = futures[future]
            try:
                future.result()
            except Exception:
                # fetch_url already logs request failures; keep the list-page context
                # so one malformed page never aborts the rest of a source.
                _fallback_content(item)

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
