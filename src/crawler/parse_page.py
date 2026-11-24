from __future__ import annotations

from html.parser import HTMLParser

from src.crawler.quality import is_low_signal_title, is_safe_http_url
from src.storage.models import InformationItem
from src.utils.text_utils import clean_text, contains_any, normalize_url

# A link's container text is only trusted as "its" context when it is reasonably small.
# Larger containers are list pages (e.g. a whole arXiv listing), where the surrounding
# text belongs to many links and would make every link match every keyword.
MAX_CONTEXT_CHARS = 600


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
            surrounding = title
            for parent in a.parents:
                if parent.name not in {"article", "li", "dd", "dt", "p", "div", "section", "tr"}:
                    continue
                text = clean_text(parent.get_text(" "))
                if len(text) > MAX_CONTEXT_CHARS:
                    break
                surrounding = text
                if parent.name in {"article", "li", "tr"}:
                    break
            yield a.get("href"), title, surrounding
    except ModuleNotFoundError:
        parser = _LinkParser()
        parser.feed(html)
        for href, title in parser.links:
            yield href, title, title


def _looks_like_content(title: str, surrounding: str) -> bool:
    if len(title) > 180:
        return False
    return not is_low_signal_title(title)


def parse_items(html: str, source: dict) -> list[InformationItem]:
    """Discover candidate content links from a generic HTML page.

    ``watch`` is an optional inexpensive pre-filter. When it is absent, the system
    deliberately keeps broad content candidates and lets the later intelligence
    layer decide what is relevant to the user.
    """
    watch = [str(x).strip() for x in source.get("watch", []) if str(x).strip()]
    max_items = max(1, int(source.get("max_items", 30)))
    items: list[InformationItem] = []
    seen: set[str] = set()

    for href_raw, title, surrounding in _links(html):
        title = clean_text(title)
        surrounding = clean_text(surrounding)
        if not _looks_like_content(title, surrounding):
            continue

        href = normalize_url(href_raw, source["url"])
        if not href or href in seen or not is_safe_http_url(href):
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
                summary=surrounding[:800],
                raw_text=surrounding,
            )
        )
        if len(items) >= max_items:
            break

    return items


# Compatibility with the old public function name.
def parse_opportunities(html: str, source: dict, keywords: dict | None = None) -> list[InformationItem]:
    return parse_items(html, source)
