import json

from src.notifier.markdown_report import generate_report


def test_report_is_domain_neutral_and_writes_json(tmp_path):
    rows = [
        {
            "title": "新的研究结果发布",
            "url": "https://example.com/research",
            "source_name": "Example Lab",
            "source_url": "https://example.com/",
            "publish_date": None,
            "deadline": None,
            "event_date": None,
            "location": None,
            "summary": "summary",
            "raw_text": "raw",
            "score": 0,
            "category": "X",
            "first_seen_at": "2026-08-18T00:00:00Z",
            "last_seen_at": "2026-08-18T00:00:00Z",
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

    path = generate_report(rows, "2026-08-18", str(tmp_path), digest=digest, source_stats={"scanned": 1, "failed": 0})
    markdown = path.read_text(encoding="utf-8")
    data = json.loads((tmp_path / "2026-08-18.json").read_text(encoding="utf-8"))

    assert "A类" not in markdown
    assert "夏令营" not in markdown
    assert "分组情报" in markdown
    assert data["digest"]["llm"]["used"] is True
