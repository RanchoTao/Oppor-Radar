import json

from src.notifier.markdown_report import generate_report


def test_report_is_domain_neutral_and_writes_structured_views(tmp_path):
    rows = [
        {
            "title": "新的研究结果发布",
            "url": "https://example.com/research",
            "source_name": "Example Lab",
            "source_url": "https://example.com/",
            "source_group": "学术",
            "publish_date": None,
            "deadline": None,
            "event_date": None,
            "location": None,
            "summary": "summary",
            "content": "content",
            "raw_text": "raw",
            "content_hash": "abc",
            "topics_json": '["AI"]',
            "importance": 0.8,
            "relevance": 0.9,
            "novelty": 0.7,
            "keep": 1,
            "reason": "相关",
            "action": "阅读原文",
            "time_sensitive": 0,
            "first_seen_at": "2026-08-18T00:00:00Z",
            "last_seen_at": "2026-08-18T00:00:00Z",
            "changed_at": "2026-08-18T00:00:00Z",
        }
    ]
    digest = {
        "headline": "今天值得关注的一条研究动态。",
        "overview": "这是一个跨领域的个性化摘要。",
        "groups": [
            {
                "name": "学术",
                "summary": "学术组有一条新动态。",
                "highlights": [
                    {
                        "title": "新的研究结果发布",
                        "why": "与研究方向相关。",
                        "action": "阅读原文。",
                        "source": "Example Lab",
                        "url": "https://example.com/research",
                    }
                ],
            }
        ],
        "cross_group_signals": [],
        "action_items": ["阅读原文。"],
        "llm": {"used": True, "model": "deepseek-v4-flash"},
    }

    path = generate_report(
        rows,
        "2026-08-18",
        str(tmp_path),
        digest=digest,
        source_stats={
            "configured": 8,
            "healthy": 7,
            "new_items": 12,
            "changed_items": 2,
            "candidate_items": 14,
            "selected_items": 1,
            "last_updated_at": "2026-08-18T08:01:00+08:00",
        },
    )
    markdown = path.read_text(encoding="utf-8")
    data = json.loads((tmp_path / "2026-08-18.json").read_text(encoding="utf-8"))
    latex = (tmp_path / "2026-08-18.tex").read_text(encoding="utf-8")

    assert "A类" not in markdown
    assert "系统状态" not in markdown
    assert "## 学术" in markdown
    assert data["schema_version"] == 2
    assert data["metrics"]["selected_items"] == 1
    assert "llm" not in data["digest"]
    assert data["items"][0]["topics"] == ["AI"]
    assert "Opportunity Radar" in latex
