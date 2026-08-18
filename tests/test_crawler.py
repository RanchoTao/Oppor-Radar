from src.crawler.content import content_hash, extract_document
from src.crawler.discovery import _hydrate_details, _should_fetch_detail
from src.crawler.feeds import parse_feed
from src.storage.models import InformationItem


def test_extract_document_removes_navigation_noise():
    html = """
    <html><head><title>Example Article</title></head><body>
      <nav>首页 联系我们</nav>
      <article><h1>重要更新</h1><p>这是正文中的核心信息。</p></article>
      <footer>版权信息</footer>
    </body></html>
    """
    document = extract_document(html)

    assert document["title"] == "Example Article"
    assert "重要更新" in document["text"]
    assert "联系我们" not in document["text"]
    assert content_hash(document["text"]) == content_hash(document["text"])


def test_parse_rss_into_generic_information_items():
    rss = """<?xml version="1.0"?>
    <rss version="2.0"><channel>
      <item>
        <title>央行发布季度报告</title>
        <link>https://example.com/report</link>
        <description>报告正文摘要。</description>
        <pubDate>Tue, 18 Aug 2026 08:00:00 GMT</pubDate>
      </item>
    </channel></rss>
    """
    source = {"name": "Example", "url": "https://example.com/", "group": "金融"}
    items = parse_feed(rss, source)

    assert len(items) == 1
    assert items[0].group == "金融"
    assert items[0].title == "央行发布季度报告"
    assert items[0].url == "https://example.com/report"


def test_external_detail_is_not_fetched_by_default():
    source = {"name": "Example", "url": "https://example.com/"}
    external = InformationItem(
        title="External item",
        url="https://other.example.net/article",
        source_name="Example",
        source_url=source["url"],
    )
    same_host = InformationItem(
        title="Local item",
        url="https://example.com/article",
        source_name="Example",
        source_url=source["url"],
    )

    assert _should_fetch_detail(external, source) is False
    assert _should_fetch_detail(same_host, source) is True
    source["fetch_external_details"] = True
    assert _should_fetch_detail(external, source) is True


def test_items_beyond_detail_budget_still_receive_fingerprint(monkeypatch):
    source = {
        "name": "Example",
        "url": "https://example.com/",
        "max_detail_items": 1,
    }
    items = [
        InformationItem(
            title="First",
            url="https://example.com/1",
            source_name="Example",
            source_url=source["url"],
            summary="first summary",
            raw_text="first context",
        ),
        InformationItem(
            title="Second",
            url="https://example.com/2",
            source_name="Example",
            source_url=source["url"],
            summary="second summary",
            raw_text="second context",
        ),
    ]

    monkeypatch.setattr(
        "src.crawler.discovery.fetch_url",
        lambda url, timeout=8: "<html><body><article>detail body</article></body></html>",
    )
    result = _hydrate_details(items, source)

    assert result[0].content_hash
    assert result[1].content_hash == content_hash("second context")
