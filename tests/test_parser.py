from src.crawler.parse_page import parse_opportunities


def keywords():
    return {
        "core": ["AI", "人工智能", "机器学习"],
        "math": ["数学", "概率"],
        "opportunity": ["夏令营", "科研训练", "本科生", "报名"],
        "negative": [],
    }


def test_source_tags_alone_do_not_make_irrelevant_navigation_candidate():
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


def test_relevant_link_text_is_kept_without_application_only_filter():
    html = """
    <html><body>
      <div>面向本科生开放 <a href="/summer">AI 科研训练报名</a></div>
      <div><a href="/paper">新的机器学习研究结果发布</a></div>
    </body></html>
    """
    source = {
        "name": "Example AI Institute",
        "url": "https://example.edu/",
        "tags": ["人工智能"],
    }

    items = parse_opportunities(html, source, keywords())

    assert len(items) == 2
    assert items[0].url == "https://example.edu/summer"
    assert items[1].url == "https://example.edu/paper"


def test_watch_keywords_support_finance_or_any_other_group():
    html = """
    <html><body>
      <div><a href="/macro">央行发布最新宏观政策报告</a></div>
      <div><a href="/sports">球队公布新赛季名单</a></div>
    </body></html>
    """
    source = {
        "name": "Example News",
        "url": "https://example.com/",
        "group": "金融",
        "watch": ["宏观", "央行"],
    }

    items = parse_opportunities(html, source, keywords())

    assert [item.title for item in items] == ["央行发布最新宏观政策报告"]
