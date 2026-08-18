from src.llm.deepseek_digest import build_daily_digest


def sample_rows():
    return [
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


def sample_sources():
    return [
        {
            "name": "Example Finance",
            "url": "https://example.com/",
            "group": "金融",
            "tags": ["宏观"],
        }
    ]


def test_digest_falls_back_without_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    digest = build_daily_digest(sample_rows(), sample_sources(), "2026-08-18")

    assert digest["llm"]["used"] is False
    assert digest["groups"][0]["name"] == "金融"
    assert digest["groups"][0]["highlights"][0]["title"] == "央行发布最新政策报告"


def test_empty_digest_does_not_call_llm(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "should-not-be-used")
    digest = build_daily_digest([], [], "2026-08-18")

    assert digest["llm"]["used"] is False
    assert digest["llm"]["reason"] == "no_new_items"


def test_successful_deepseek_json_response(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "model": "deepseek-v4-flash",
                "choices": [
                    {
                        "message": {
                            "content": '{"headline":"今日宏观信号","overview":"有一条重要更新。","groups":[{"name":"金融","summary":"宏观更新","highlights":[]}],"cross_group_signals":[],"action_items":[]}'
                        }
                    }
                ],
            }

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["payload"] = json
        captured["headers"] = headers
        return FakeResponse()

    monkeypatch.setattr("src.llm.deepseek_digest.requests.post", fake_post)

    digest = build_daily_digest(sample_rows(), sample_sources(), "2026-08-18")

    assert digest["llm"]["used"] is True
    assert digest["llm"]["model"] == "deepseek-v4-flash"
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["payload"]["response_format"] == {"type": "json_object"}
    assert captured["payload"]["thinking"] == {"type": "disabled"}
    assert captured["headers"]["Authorization"] == "Bearer test-key"
