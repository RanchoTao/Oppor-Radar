"""Regression tests for the failure modes found in the Nov 2026 audit."""

from src.crawler.discovery import _hydrate_details
from src.crawler.feeds import parse_feed
from src.crawler.parse_page import parse_items
from src.crawler.quality import is_low_signal_title
from src.llm import deepseek_digest
from src.llm.deepseek_digest import _fallback_item_result, rank_items
from src.storage.db import connect, upsert_item
from src.storage.models import InformationItem


def test_navigation_and_format_links_are_low_signal():
    for title in [
        "Skip to main content", "News", "Products", "FEATURED", "Learn More", "html",
        "other", "1Introduction", "Back to Careers", "Select Year: (2027)", "教师主页系统",
        "现任领导_中国人民大学高瓴人工智能学院", "Format selector for 2610.02202",
    ]:
        assert is_low_signal_title(title), title
    for title in [
        "Call for Papers", "Lean Graph Search for Formal Theorem Proving",
        "工作坊 - 北京雁栖湖应用数学研究院", "首届地瓜机器人黑客松",
    ]:
        assert not is_low_signal_title(title), title


def test_listing_page_context_does_not_leak_keywords_to_every_link():
    # One big container with many entries: the keyword appears only in entry A.
    entries = "".join(
        f'<dt><a href="/abs/{i}">arXiv:{i}</a> <a href="/html/{i}">html</a> <a href="/format/{i}">other</a></dt>'
        f'<dd><div class="title">Title {i} about {"agent planning" if i == 1 else "protein folding"} methods</div></dd>'
        for i in range(1, 30)
    )
    html = f"<html><body><div id='list'><dl>{entries}</dl></div></body></html>"
    source = {"name": "arXiv", "url": "https://arxiv.org/list/cs.AI/recent", "watch": ["agent"]}
    titles = [item.title for item in parse_items(html, source)]
    assert "html" not in titles and "other" not in titles


def test_feed_entries_without_link_are_skipped_not_collapsed_onto_source_url():
    rss = """<rss><channel>
      <item><title>Entry without link one</title><description>a</description></item>
      <item><title>Entry without link two</title><description>b</description></item>
      <item><title>Entry with link</title><link>https://example.com/x</link></item>
      <item><title>Script link</title><link>javascript:alert(1)</link></item>
    </channel></rss>"""
    items = parse_feed(rss, {"name": "S", "url": "https://example.com/"})
    assert [item.url for item in items] == ["https://example.com/x"]


def _item(content: str, basis: str) -> InformationItem:
    from src.crawler.content import content_hash

    return InformationItem(
        title="Mathlib release notes",
        url="https://example.com/release",
        source_name="S",
        source_url="https://example.com",
        content=content,
        content_hash=content_hash(content),
        hash_basis=basis,
    )


def test_detail_fetch_failure_does_not_flip_item_to_changed(tmp_path):
    conn = connect(str(tmp_path / "db.sqlite3"))
    body = " ".join(f"Change {i}: refactor module {i * 11} for performance." for i in range(60))
    assert upsert_item(conn, _item(body, "detail")) == "new"
    # Next run the detail budget is exhausted: only the listing snippet is available.
    assert upsert_item(conn, _item("Release notes snippet", "listing")) == "unchanged"
    # And the run after, the full page is back: still not a change.
    assert upsert_item(conn, _item(body, "detail")) == "unchanged"


def test_small_page_noise_is_not_a_material_change(tmp_path):
    conn = connect(str(tmp_path / "db.sqlite3"))
    body = " ".join(f"Paragraph {i} discusses lemma {i * 7} and tactic {i * 13} in Lean." for i in range(80))
    assert upsert_item(conn, _item(body + " Views: 120 · 3 days ago", "detail")) == "new"
    assert upsert_item(conn, _item(body + " Views: 168 · 4 days ago", "detail")) == "unchanged"
    rewritten = " ".join(f"Section {i}: applicants from cohort {i * 3} must register by day {i}." for i in range(80))
    assert upsert_item(conn, _item(rewritten, "detail")) == "changed"


def _row(i: int) -> dict:
    return {
        "title": f"Lean theorem proving release number {i}",
        "url": f"https://example.com/{i}",
        "source_name": "S",
        "source_url": "https://example.com",
        "source_group": "数学 / AI for Math",
        "content": "Lean automated theorem proof release",
        "summary": "",
        "raw_text": "",
    }


def test_rank_items_falls_back_per_batch_and_for_unmatched_rows(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "k")
    monkeypatch.setenv("OPPOR_LLM_ITEM_BATCH", "2")
    calls = {"n": 0}

    def fake_post(system_prompt, payload, **kwargs):
        calls["n"] += 1
        ids = [item["id"] for item in payload["items"]]
        if calls["n"] == 2:
            raise RuntimeError("boom")
        # Model drops the second item and mangles the URL of the first.
        return {"items": [{"id": ids[0], "keep": False, "url": "https://EXAMPLE.com/x/", "relevance": 0.1}]}, "deepseek-flash"

    monkeypatch.setattr(deepseek_digest, "_post_json", fake_post)
    rows = [_row(i) for i in range(5)]
    results, meta = rank_items(rows, [{"name": "S", "url": "https://example.com"}], {})

    assert len(results) == len(rows)
    assert [r["url"] for r in results] == [row["url"] for row in rows]
    assert results[0]["keep"] is False  # model verdict applied, identity from our row
    assert meta["used"] is True
    assert meta["model_items"] == 2  # rows 0 and 4
    assert meta["fallback_items"] == 3
    assert meta["reason"] == "partial_api_failure"


def test_fallback_rejects_junk_even_from_authoritative_source():
    source = {"name": "S", "authority": 0.95, "sections": ["ai", "research"]}
    junk = {"title": "Skip to main content", "summary": "agent reasoning release", "url": "u", "source_name": "S"}
    assert _fallback_item_result(junk, source, {"interests": ["AI Agent"]})["keep"] is False

    plain = {"title": "Company picnic photos from our offsite", "summary": "fun day", "url": "u", "source_name": "S"}
    assert _fallback_item_result(plain, source, {"interests": ["AI Agent"]})["keep"] is False

    relevant = {
        "title": "Introducing a new agent benchmark for long-horizon tasks",
        "summary": "We release an AI agent benchmark.", "url": "u", "source_name": "S",
    }
    assert _fallback_item_result(relevant, source, {"interests": ["AI Agent 与长期任务"]})["keep"] is True
