from __future__ import annotations

from html.parser import HTMLParser
from src.storage.models import Opportunity
from src.utils.text_utils import clean_text, normalize_url, contains_any

class _LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self._href=None; self._text=[]
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self._href = dict(attrs).get('href'); self._text=[]
    def handle_data(self, data):
        if self._href is not None: self._text.append(data)
    def handle_endtag(self, tag):
        if tag == 'a' and self._href is not None:
            self.links.append((self._href, clean_text(' '.join(self._text))))
            self._href=None; self._text=[]

def _links(html: str):
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a"):
            title = clean_text(a.get_text(" "))
            surrounding = clean_text(a.parent.get_text(" ") if a.parent else title)
            yield a.get("href"), title, surrounding
    except ModuleNotFoundError:
        parser = _LinkParser(); parser.feed(html)
        for href, title in parser.links:
            yield href, title, title


def parse_opportunities(html: str, source: dict, keywords: dict) -> list[Opportunity]:
    wanted = sum((keywords.get(k, []) for k in ("core", "math", "opportunity")), [])
    items: list[Opportunity] = []
    seen: set[str] = set()
    for href_raw, title, surrounding in _links(html):
        if len(title) < 4:
            continue
        href = normalize_url(href_raw, source["url"])
        if not href or href in seen:
            continue
        tags_text = " ".join(source.get("tags", []))
        if not contains_any(f"{title} {surrounding} {tags_text}", wanted):
            continue
        seen.add(href)
        items.append(Opportunity(title=title, url=href, source_name=source["name"], source_url=source["url"], summary=surrounding[:300], raw_text=surrounding))
    return items
