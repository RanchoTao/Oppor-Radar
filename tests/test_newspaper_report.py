import json

from src.notifier.markdown_report import generate_report


def test_report_publishes_newspaper_and_eight_page_tex(tmp_path):
    row = {
        "title": "New frontier model",
        "url": "https://example.com/model",
        "source_name": "Example Lab",
        "source_url": "https://example.com/",
        "source_group": "AI / 前沿研究",
        "publish_date": "2026-09-08",
        "deadline": None,
        "event_date": None,
        "location": None,
        "summary": "A major model update.",
        "content": "A major model update.",
        "raw_text": "A major model update.",
        "content_hash": "abc",
        "topics_json": '["AI"]',
        "importance": 0.9,
        "relevance": 0.95,
        "novelty": 0.8,
        "keep": 1,
        "reason": "Relevant to frontier AI.",
        "action": "仅供了解",
        "time_sensitive": 0,
        "first_seen_at": "2026-09-08T01:00:00Z",
        "last_seen_at": "2026-09-08T01:00:00Z",
        "changed_at": "2026-09-08T01:00:00Z",
    }
    digest = {
        "headline": "Today matters.",
        "overview": "One important update.",
        "groups": [],
        "cross_group_signals": [],
        "action_items": [],
        "llm": {"used": False},
    }
    ids = ["front", "ai", "research", "math", "opportunity", "engineering", "business", "world"]
    newspaper = {
        "edition": "OR Morning",
        "report_date": "2026-09-08",
        "pages": [
            {
                "id": page_id,
                "title": page_id,
                "subtitle": "subtitle",
                "headline": "New frontier model" if page_id in {"front", "ai"} else "",
                "overview": "overview",
                "items": [
                    {
                        "title": "New frontier model",
                        "summary": "A major model update.",
                        "why": "Relevant to frontier AI.",
                        "action": "",
                        "source": "Example Lab",
                        "url": "https://example.com/model",
                    }
                ] if page_id in {"front", "ai"} else [],
            }
            for page_id in ids
        ],
        "llm": {"used": False, "reason": "test"},
    }

    generate_report(
        [row],
        "2026-09-08",
        str(tmp_path),
        digest=digest,
        newspaper=newspaper,
        source_stats={"configured": 1, "healthy": 1, "selected_items": 1},
    )

    payload = json.loads((tmp_path / "2026-09-08.json").read_text(encoding="utf-8"))
    tex = (tmp_path / "2026-09-08.tex").read_text(encoding="utf-8")

    assert payload["newspaper"]["edition"] == "OR Morning"
    assert [page["id"] for page in payload["newspaper"]["pages"]] == ids
    assert payload["diagnostics"]["newspaper_editor"]["reason"] == "test"
    assert tex.count("\\newpage") == 7
    assert "OR MORNING / SECTION 08" in tex
