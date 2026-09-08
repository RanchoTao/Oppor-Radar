from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urlparse

from src.storage.models import InformationItem
from src.utils.text_utils import clean_text, contains_any, normalize_url


NAVIGATION_TEXT = {
    "首页", "主页", "关于我们", "联系我们", "网站地图", "english", "en",
    "登录", "注册", "更多", "more", "返回顶部", "下一页", "上一页",
    "home", "about", "contact", "privacy", "terms", "cookies", "developers",
    "research", "models", "careers", "people", "team", "news", "blog",
    "explore models", "explore research", "skip to main content", "view all",
    "learn more", "read more", "see all", "select year", "all news",
}

NAVIGATION_PREFIXES = (
    "首页", "关于", "联系", "导航", "菜单", "版权", "隐私", "登录", "注册",
    "skip to", "explore ", "select year", "view all", "see all", "back to",
)

GENERIC_TITLES = {
    "2026 conference", "2027 conference", "conference", "latest announcements",
    "quick links", "resources", "publications", "events", "press", "company",
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


def _compact_context(a, title: str) -> tuple[str, str | None]:
    """Choose the smallest article-like ancestor instead of swallowing site navigation."""
    publish_date = None
    chosen = None
    for parent in a.parents:
        if getattr(parent, "name", None) not in {"article", "li", "p", "div", "section"}:
            continue
        text = clean_text(parent.get_text(" "))
        if len(text) < len(title):
            continue
        time_node = parent.find("time") if hasattr(parent, "find") else None
        if time_node is not None:
            publish_date = clean_text(time_node.get("datetime") or time_node.get_text(" ")) or None
        if len(text) <= 1400:
            chosen = text
            break
    return (chosen or title)[:1400], publish_date


def _links(html: str):
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a"):
            title = clean_text(a.get_text(" "))
            surrounding, publish_date = _compact_context(a, title)
            yield a.get("href"), title, surrounding, publish_date
    except ModuleNotFoundError:
        parser = _LinkParser()
        parser.feed(html)
        for href, title in parser.links:
            yield href, title, title, None


def _looks_like_content(title: str, surrounding: str, source: dict) -> bool:
    if len(title) < 5 or len(title) > 180:
        return False
    lower = title.strip().lower().rstrip(":")
    if lower in NAVIGATION_TEXT or lower in GENERIC_TITLES:
        return False
    if any(lower.startswith(prefix) for prefix in NAVIGATION_PREFIXES):
        return False
    if title in NAVIGATION_TEXT or any(title.startswith(prefix) for prefix in NAVIGATION_PREFIXES):
        return False
    if lower.isdigit() or (len(lower) <= 8 and lower.replace("-", "").isdigit()):
        return False
    excludes = [str(x).strip().lower() for x in source.get("exclude_titles", []) if str(x).strip()]
    if any(term == lower or term in lower for term in excludes):
        return False
    return len(surrounding) >= len(title)


def _url_allowed(url: str, source: dict) -> bool:
    lower = url.lower()
    includes = [str(x).strip().lower() for x in source.get("include_url_patterns", []) if str(x).strip()]
    excludes = [str(x).strip().lower() for x in source.get("exclude_url_patterns", []) if str(x).strip()]
    if includes and not any(pattern in lower for pattern in includes):
        return False
    if excludes and any(pattern in lower for pattern in excludes):
        return False

    # Generic safety net: anchors pointing only to a site's root/category pages are often navigation.
    parsed = urlparse(url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) == 0:
        return False
    return True


def parse_items(html: str, source: dict) -> list[InformationItem]:
    """Discover candidate content links from a generic HTML page.

    ``watch`` is an optional inexpensive pre-filter. URL/title filters allow broad
    institutional homepages to act like focused source adapters without bespoke code.
    """
    watch = [str(x).strip() for x in source.get("watch", []) if str(x).strip()]
    max_items = max(1, int(source.get("max_items", 30)))
    items: list[InformationItem] = []
    seen: set[str] = set()

    for href_raw, title, surrounding, publish_date in _links(html):
        title = clean_text(title)
        surrounding = clean_text(surrounding)
        if not _looks_like_content(title, surrounding, source):
            continue

        href = normalize_url(href_raw, source["url"])
        if not href or href in seen:
            continue
        if href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        if not _url_allowed(href, source):
            continue

        candidate_text = f"{title} {surrounding}"
        if watch and not contains_any(candidate_text, watch):
            continue

        seen.add(href)
        items.append(
            InformationItem(
                title=title,
                url=href,
                source_name=source["name"],
                source_url=source["url"],
                group=source.get("group", "未分组"),
                publish_date=publish_date,
                summary=surrounding[:900],
                raw_text=surrounding,
            )
        )
        if len(items) >= max_items:
            break

    return items


# Compatibility with the old public function name.
def parse_opportunities(html: str, source: dict, keywords: dict | None = None) -> list[InformationItem]:
    return parse_items(html, source)
