from __future__ import annotations

import xml.etree.ElementTree as ET
from urllib.parse import urljoin

from src.storage.models import InformationItem
from src.utils.text_utils import clean_text


def discover_feed_urls(html: str, base_url: str) -> list[str]:
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        urls: list[str] = []
        for link in soup.find_all("link"):
            rel = " ".join(link.get("rel") or []).lower()
            kind = (link.get("type") or "").lower()
            href = link.get("href")
            if href and "alternate" in rel and ("rss" in kind or "atom" in kind or "xml" in kind):
                url = urljoin(base_url, href)
                if url not in urls:
                    urls.append(url)
        return urls[:4]
    except ModuleNotFoundError:
        return []


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(node: ET.Element, names: set[str]) -> str:
    for child in list(node):
        if _local(child.tag) in names:
            return clean_text("".join(child.itertext()))
    return ""


def parse_feed(xml_text: str, source: dict) -> list[InformationItem]:
    """Parse common RSS/Atom feeds without an extra dependency."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    max_items = max(1, int(source.get("max_items", 30)))
    entries = [node for node in root.iter() if _local(node.tag) in {"item", "entry"}]
    result: list[InformationItem] = []

    for entry in entries[:max_items]:
        title = _child_text(entry, {"title"})
        if not title:
            continue

        link = _child_text(entry, {"link", "guid"})
        if not link:
            for child in list(entry):
                if _local(child.tag) == "link" and child.attrib.get("href"):
                    link = child.attrib["href"]
                    break
        link = urljoin(source["url"], link) if link else source["url"]

        summary = _child_text(entry, {"description", "summary", "content"})
        published = _child_text(entry, {"pubdate", "published", "updated", "date"}) or None
        result.append(
            InformationItem(
                title=title,
                url=link,
                source_name=source["name"],
                source_url=source["url"],
                group=source.get("group", "未分组"),
                publish_date=published,
                summary=summary[:1200],
                raw_text=summary,
            )
        )

    return result
