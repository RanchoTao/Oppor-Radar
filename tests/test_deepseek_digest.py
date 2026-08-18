from src.llm.deepseek_digest import build_daily_digest


def test_digest_falls_back_without_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    rows = [
        {
            "title": "央行发布最新政策报告",
            "url": "https://example.com/macro",
            "source_name": "Example Finance",
            "source_url": "https://example.com/",
            "summary": "一段关于宏观政策的新信息。",
            "raw_text": "一段关于宏观政策的新信息。",
            "publish_date": None,
            "deadline": None,
            "event_date": None,
            "location": None,
        }
    ]
    sources = [
        {
            "name": "Example Finance",
            "url": "https://example.com/",
            "group": "金融",
            "tags": ["宏观"],
        }
    ]

    digest = build_daily_digest(rows, sources, "2026-08-18")

    assert digest["llm"]["used"] is False
    assert digest["groups"][0]["name"] == "金融"
    assert digest["groups"][0]["highlights"][0]["title"] == "央行发布最新政策报告"


def test_empty_digest_does_not_call_llm(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "should-not-be-used")
    digest = build_daily_digest([], [], "2026-08-18")

    assert digest["llm"]["used"] is False
    assert digest["llm"]["reason"] == "no_new_items"
