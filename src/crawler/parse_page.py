from __future__ import annotations

from html.parser import HTMLParser

from src.storage.models import Opportunity
from src.utils.text_utils import clean_text, contains_any, normalize_url


NAVIGATION_TEXT = {
    "首页",
    "主页",
    "关于我们",
    "联系我们",
    "网站地图",
    "English",
    "EN",
    "登录",
    "注册",
    "更多",
    "more",
    "返回顶部",
}


class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None
        self._text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, clean_text(" ".join(self._text))))
            self._href = None
            self._text = []


def _links(html: str):
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a"):
            title = clean_text(a.get_text(" "))
            surrounding = clean_text(a.parent.get_text(" ") if a.parent else title)
            yield a.get("href"), title, surrounding
    except ModuleNotFoundError:
        parser = _LinkParser()
        parser.feed(html)
        for href, title in parser.links:
            yield href, title, title


def parse_opportunities(html: str, source: dict, keywords: dict | None = None) -> list[Opportunity]:
    """Extract feed-like items from any user-selected webpage.

    Opportunity Radar is no longer limited to admissions/applications. A source can
    optionally define ``watch`` keywords to restrict what is collected. Without a
    watch list, the crawler keeps contentful links and delegates relevance ranking
    to the LLM layer. Obvious navigation links are always discarded.
    """
    watch = [str(x) for x in source.get("watch", []) if str(x).strip()]
    max_items = int(source.get("max_items", 30))
    items: list[Opportunity] = []
    seen: set[str] = set()

    for href_raw, title, surrounding in _links(html):
        title = clean_text(title)
        if len(title) < 4 or title in NAVIGATION_TEXT:
            continue

        href = normalize_url(href_raw, source["url"])
        if not href or href in seen:
            continue

        candidate_text = f"{title} {surrounding}"
        if watch and not contains_any(candidate_text, watch):
            continue

        seen.add(href)
        items.append(
            Opportunity(
                title=title,
                url=href,
                source_name=source["name"],
                source_url=source["url"],
                summary=surrounding[:500],
                raw_text=surrounding,
            )
        )
        if len(items) >= max_items:
            break

    return items
