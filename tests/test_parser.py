from src.crawler.parse_page import parse_items


def test_navigation_is_not_a_candidate():
    html = """
    <html><body>
      <div><a href="/about">联系我们</a></div>
    </body></html>
    """
    source = {
        "name": "Example AI Institute",
        "url": "https://example.edu/",
        "group": "学术",
        "tags": ["人工智能", "数学"],
    }

    assert parse_items(html, source) == []


def test_domain_neutral_content_links_are_kept():
    html = """
    <html><body>
      <div>面向本科生开放 <a href="/summer">AI 科研训练报名</a></div>
      <div><a href="/paper">新的机器学习研究结果发布</a></div>
      <div><a href="/macro">央行发布季度货币政策执行报告</a></div>
    </body></html>
    """
    source = {
        "name": "Example Feed",
        "url": "https://example.edu/",
        "group": "综合",
    }

    items = parse_items(html, source)

    assert len(items) == 3
    assert items[0].group == "综合"
    assert items[2].url == "https://example.edu/macro"


def test_watch_keywords_support_any_group():
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

    items = parse_items(html, source)
    assert [item.title for item in items] == ["央行发布最新宏观政策报告"]
