from src.crawler.discovery import CrawlResult
from src.scheduler.run_daily import _crawl_all_sources


def test_crawl_all_sources_preserves_registry_order(monkeypatch):
    sources = [
        {"name": "A", "url": "https://a.example", "group": "学术"},
        {"name": "B", "url": "https://b.example", "group": "金融"},
    ]

    def fake_crawl(source):
        return CrawlResult([], "ok", source["name"], mode="html")

    monkeypatch.setattr("src.scheduler.run_daily.crawl_source", fake_crawl)
    results = _crawl_all_sources(sources)

    assert [source["name"] for source, _ in results] == ["A", "B"]
    assert all(result.status == "ok" for _, result in results)


def test_crawl_all_sources_isolates_source_exception(monkeypatch):
    sources = [
        {"name": "good", "url": "https://good.example"},
        {"name": "bad", "url": "https://bad.example"},
    ]

    def fake_crawl(source):
        if source["name"] == "bad":
            raise RuntimeError("boom")
        return CrawlResult([], "ok")

    monkeypatch.setattr("src.scheduler.run_daily.crawl_source", fake_crawl)
    results = dict((source["name"], result) for source, result in _crawl_all_sources(sources))

    assert results["good"].status == "ok"
    assert results["bad"].status == "error"
    assert "boom" in results["bad"].message
