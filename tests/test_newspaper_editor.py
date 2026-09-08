from src.llm.newspaper_editor import SECTION_DEFS, build_newspaper


def row(title, source_name, group, summary, reason, *, importance=0.9, relevance=0.9, novelty=0.8, action="仅供了解"):
    return {
        "title": title,
        "url": f"https://example.com/{title.replace(' ', '-').lower()}",
        "source_name": source_name,
        "source_url": "https://example.com/",
        "source_group": group,
        "summary": summary,
        "content": summary,
        "raw_text": summary,
        "topics_json": "[]",
        "importance": importance,
        "relevance": relevance,
        "novelty": novelty,
        "reason": reason,
        "action": action,
        "time_sensitive": 0,
        "publish_date": "2026-09-08",
        "deadline": None,
        "first_seen_at": "2026-09-08T01:00:00Z",
        "changed_at": "2026-09-08T01:00:00Z",
    }


def sources():
    return [
        {
            "name": "Frontier Lab",
            "url": "https://example.com/lab",
            "group": "AI / 前沿研究",
            "sections": ["ai", "research"],
            "source_type": "primary",
            "authority": 1.0,
        },
        {
            "name": "Math Lab",
            "url": "https://example.com/math",
            "group": "数学 / AI for Math",
            "sections": ["math", "research"],
            "source_type": "research",
            "authority": 0.95,
        },
        {
            "name": "Opportunity Lab",
            "url": "https://example.com/opportunity",
            "group": "科研 / 机会",
            "sections": ["opportunity", "research"],
            "source_type": "opportunity",
            "authority": 0.95,
        },
    ]


def test_newspaper_fallback_has_exactly_eight_sections(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    rows = [
        row(
            "New agent reasoning model released",
            "Frontier Lab",
            "AI / 前沿研究",
            "A frontier lab released a new agent reasoning model.",
            "Directly relevant to frontier AI and agents.",
        ),
        row(
            "Lean theorem proving result",
            "Math Lab",
            "数学 / AI for Math",
            "A new Lean theorem proving result was published.",
            "Relevant to AI for Mathematics.",
        ),
        row(
            "Research internship application opens",
            "Opportunity Lab",
            "科研 / 机会",
            "A research internship opened applications with a deadline.",
            "This is directly actionable.",
            action="检查资格并决定是否申请。",
        ),
    ]

    newspaper = build_newspaper(rows, sources(), "2026-09-08", {"interests": ["Agent", "Lean"]})

    assert newspaper["llm"]["used"] is False
    assert [page["id"] for page in newspaper["pages"]] == [section["id"] for section in SECTION_DEFS]
    assert len(newspaper["pages"]) == 8
    assert len(newspaper["pages"][0]["items"]) <= 7
    assert all(len(page["items"]) <= 5 for page in newspaper["pages"][1:])


def test_source_section_hints_place_items_in_expected_pages(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    rows = [
        row(
            "New agent reasoning model released",
            "Frontier Lab",
            "AI / 前沿研究",
            "A frontier lab released a new agent reasoning model.",
            "Directly relevant to frontier AI and agents.",
        ),
        row(
            "Lean theorem proving result",
            "Math Lab",
            "数学 / AI for Math",
            "A new Lean theorem proving result was published.",
            "Relevant to AI for Mathematics.",
        ),
        row(
            "Research internship application opens",
            "Opportunity Lab",
            "科研 / 机会",
            "A research internship opened applications with a deadline.",
            "This is directly actionable.",
        ),
    ]

    newspaper = build_newspaper(rows, sources(), "2026-09-08", {})
    pages = {page["id"]: page for page in newspaper["pages"]}

    assert any(item["source"] == "Frontier Lab" for item in pages["ai"]["items"])
    assert any(item["source"] == "Math Lab" for item in pages["math"]["items"])
    assert any(item["source"] == "Opportunity Lab" for item in pages["opportunity"]["items"])
