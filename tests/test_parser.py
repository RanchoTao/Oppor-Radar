from src.crawler.parse_page import parse_opportunities


def keywords():
    return {
        "core": ["AI", "人工智能", "机器学习"],
        "math": ["数学", "概率"],
        "opportunity": ["夏令营", "科研训练", "本科生", "报名"],
        "negative": [],
    }


def test_source_tags_alone_do_not_make_irrelevant_link_a_candidate():
    html = """
    <html><body>
      <div><a href="/about">联系我们</a></div>
    </body></html>
    """
    source = {
        "name": "Example AI Institute",
        "url": "https://example.edu/",
        "tags": ["人工智能", "数学"],
    }

    items = parse_opportunities(html, source, keywords())

    assert items == []


def test_relevant_link_text_is_kept():
    html = """
    <html><body>
      <div>面向本科生开放 <a href="/summer">AI 科研训练报名</a></div>
    </body></html>
    """
    source = {
        "name": "Example AI Institute",
        "url": "https://example.edu/",
        "tags": ["人工智能"],
    }

    items = parse_opportunities(html, source, keywords())

    assert len(items) == 1
    assert items[0].title == "AI 科研训练报名"
    assert items[0].url == "https://example.edu/summer"
