"""Cheap, deterministic checks that reject obvious non-content before any model sees it.

These run in two places:

* HTML link discovery, so navigation / chrome links never enter the database.
* The deterministic fallback ranker, so rows that slipped in earlier are not published.
"""

from __future__ import annotations

import re

# Exact (case-insensitive) anchor texts that are site chrome, not content.
NAVIGATION_TITLES = {
    # Chinese
    "首页", "主页", "关于我们", "联系我们", "网站地图", "登录", "注册", "更多", "返回顶部",
    "下一页", "上一页", "教师主页系统", "招贤纳士", "学术报告", "师资队伍", "学院简介",
    "组织机构", "机构设置", "人才队伍", "校友", "新闻中心", "通知公告", "学院新闻",
    # English
    "english", "en", "more", "read more", "learn more", "see more", "view more", "view all",
    "see all", "show more", "load more", "continue reading", "skip to main content",
    "skip to content", "skip navigation", "main menu", "menu", "search", "submit", "subscribe",
    "sign in", "sign up", "log in", "login", "register", "contact", "contact us", "about",
    "about us", "home", "news", "blog", "research", "products", "product", "pricing",
    "company", "careers", "jobs", "team", "people", "faculty", "postdocs", "engineering",
    "featured", "events", "resources", "docs", "documentation", "privacy", "privacy policy",
    "terms", "terms of service", "cookie policy", "cookies", "sitemap", "site map",
    "overview", "history", "rss", "feed", "share", "twitter", "x", "linkedin", "github",
    "youtube", "facebook", "instagram", "wechat", "weibo", "next", "previous", "prev",
    "back", "top", "back to top",
    # arXiv listing format links and similar file-format anchors
    "html", "other", "pdf", "ps", "abs", "src", "source", "bibtex", "tex", "download",
}

NAVIGATION_PREFIXES = (
    "首页", "关于", "联系", "导航", "菜单", "版权", "隐私", "登录", "注册",
    "back to ", "skip to ", "select year", "go to ", "return to ", "format selector",
)

# Titles that are almost always institutional pages rather than news.
LOW_SIGNAL_TITLE_TERMS = (
    "about us", "contact", "privacy", "terms of", "cookie", "site map", "学院简介", "师资队伍",
    "教师主页", "联系我们", "网站地图", "学科方向", "组织机构", "机构设置", "人才队伍", "现任领导",
    "行政机构", "数说学院", "历任领导",
)

_CJK = re.compile(r"[一-鿿]")
_ALNUM_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’\-.]*")


def _meaningful_length_ok(title: str) -> bool:
    """CJK titles need ~5 characters, Latin titles need ~3 words or 18 characters."""
    cjk = len(_CJK.findall(title))
    if cjk >= 5:
        return True
    words = _ALNUM_WORD.findall(title)
    if cjk and cjk + len(words) >= 5:
        return True
    return len(words) >= 3 or len(title) >= 18


def is_navigation_title(title: str) -> bool:
    text = re.sub(r"\s+", " ", (title or "")).strip()
    lower = text.lower().strip(" :：|·-→›»↗")
    if not lower:
        return True
    if lower in NAVIGATION_TITLES:
        return True
    if any(lower.startswith(prefix) for prefix in NAVIGATION_PREFIXES):
        return True
    # Pure numbers / dates / pagination ("2", "2027", "1Introduction" style section anchors).
    if re.fullmatch(r"[\d\s./\-:]+", lower):
        return True
    if re.fullmatch(r"\d+(\.\d+)*\s*[a-z]+", lower):
        return True
    return False


def is_low_signal_title(title: str) -> bool:
    """True when a title is navigation, too short to be an article, or an institutional page."""
    text = re.sub(r"\s+", " ", (title or "")).strip()
    if is_navigation_title(text):
        return True
    if not _meaningful_length_ok(text):
        return True
    lower = text.lower()
    return any(term in lower for term in LOW_SIGNAL_TITLE_TERMS)


def is_safe_http_url(url: str | None) -> bool:
    return bool(url) and str(url).lower().startswith(("http://", "https://"))
