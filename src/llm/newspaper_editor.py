from __future__ import annotations

import json
import logging
import re
from typing import Any

from src.llm.deepseek_digest import _client_config, _post_json, _profile_text, _source_meta

LOGGER = logging.getLogger(__name__)

SECTION_DEFS = [
    {
        "id": "front",
        "title": "今日总览",
        "subtitle": "如果今天只能看三分钟，这一版必须已经足够。",
        "limit": 7,
    },
    {
        "id": "opportunity",
        "title": "机会雷达",
        "subtitle": "北京、全国与线上真正可报名的 Hackathon、竞赛、科研招募、实习、Workshop 与截止。",
        "limit": 6,
    },
    {
        "id": "research",
        "title": "科研前沿",
        "subtitle": "真正会改变你接下来怎么做研究、怎么写、怎么投的信号。",
        "limit": 5,
    },
    {
        "id": "ai",
        "title": "AI Frontier",
        "subtitle": "Frontier model、Agent、RL、Reasoning、Safety。",
        "limit": 5,
    },
    {
        "id": "math",
        "title": "数学 × AI",
        "subtitle": "AI for Mathematics、Lean、证明与重要数学进展。",
        "limit": 5,
    },
    {
        "id": "engineering",
        "title": "Engineering",
        "subtitle": "开源、框架、GPU、推理基础设施与真正值得使用的新工具。",
        "limit": 5,
    },
    {
        "id": "business",
        "title": "AI 商业 / 产业",
        "subtitle": "公司、融资、市场与可能改变 AI 发展路径的产业信号。",
        "limit": 5,
    },
    {
        "id": "world",
        "title": "世界状态",
        "subtitle": "重大政策、国际、宏观与不应因为沉浸在 AI 中而错过的变化。",
        "limit": 5,
    },
]

SECTION_IDS = {section["id"] for section in SECTION_DEFS if section["id"] != "front"}

KEYWORDS = {
    "ai": [
        " ai ", "gpt", "llm", "agent", "agentic", "claude", "gemini", "qwen",
        "openai", "anthropic", "deepmind", "reinforcement", "reasoning", "alignment",
        "interpretability", "大模型", "智能体", "强化学习", "推理", "对齐", "可解释",
    ],
    "research": [
        "paper", "arxiv", "openreview", "iclr", "icml", "neurips", "research", "benchmark",
        "conference", "workshop", "dataset", "论文", "研究", "顶会", "基准", "数据集", "会议",
    ],
    "math": [
        "math", "mathemat", "lean", "theorem", "proof", "geometry", "algebra", "probability",
        "sde", "formal", "数学", "定理", "证明", "形式化", "几何", "代数", "概率", "随机微分",
    ],
    "opportunity": [
        "deadline", "cfp", "internship", "fellowship", "scholarship", "summer school",
        "winter school", "call for", "application", "apply", "residency", "hackathon", "competition",
        "contest", "meetup", "developer event", "招生", "报名", "截止", "实习", "奖学金", "招聘",
        "申请", "暑校", "访问", "资助", "黑客松", "竞赛", "比赛", "挑战赛", "活动", "招募",
        "科研训练", "本科生", "学生", "开发者", "高校",
    ],
    "engineering": [
        "github", "pytorch", "cuda", "vllm", "sglang", "inference", "serving", "kernel",
        "open source", "framework", "developer", "开源", "推理系统", "部署", "框架", "工具", "gpu",
    ],
    "business": [
        "funding", "ipo", "revenue", "earnings", "acquisition", "startup", "market", "nvidia",
        "融资", "上市", "财报", "并购", "创业", "公司", "商业", "产业", "市场",
    ],
    "world": [
        "policy", "regulation", "government", "federal reserve", "white house", "european commission",
        "geopolit", "monetary", "政策", "监管", "国际", "中美", "全球", "宏观", "央行", "政府",
    ],
}

GROUP_SECTION_HINTS = {
    "机会 / 本地与在线": ["opportunity", "research", "engineering"],
    "AI / 前沿研究": ["ai", "research"],
    "数学 / AI for Math": ["math", "research"],
    "科研 / 机会": ["research", "opportunity"],
    "工程 / 开源": ["engineering", "ai"],
    "产业 / 金融": ["business"],
    "世界 / 政策": ["world"],
    "学术": ["research", "opportunity"],
    "AI / 科技": ["ai", "engineering"],
    "金融": ["business", "world"],
    "社会 / 政策": ["world"],
}


def _value(row, key: str, default=None):
    try:
        value = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if value is None else value


def _bounded_float(value, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _source_sections(source: dict) -> list[str]:
    explicit = [str(x).strip() for x in source.get("sections", []) if str(x).strip() in SECTION_IDS]
    if explicit:
        return explicit
    return GROUP_SECTION_HINTS.get(str(source.get("group") or ""), [])


def _matched_sections(item: dict) -> list[str]:
    sections = list(item.get("source_sections") or [])
    text = f" {item.get('title', '')} {item.get('summary', '')} {item.get('topics_text', '')} ".lower()
    for section_id, words in KEYWORDS.items():
        if any(word in text for word in words) and section_id not in sections:
            sections.append(section_id)
    return [section for section in sections if section in SECTION_IDS]


def _normalize_title(title: str) -> str:
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", (title or "").lower())
    return text[:180]


def _item_score(item: dict) -> float:
    base = (
        0.38 * item["relevance"]
        + 0.30 * item["importance"]
        + 0.12 * item["novelty"]
        + 0.10 * item["authority"]
        + (0.05 if item.get("time_sensitive") else 0.0)
    )
    if "opportunity" in item.get("sections", []):
        base += 0.20 * item.get("reachability", 0.45)
        if item.get("deadline"):
            base += 0.04
    return round(min(1.0, base), 4)


def _editor_item(row, source: dict) -> dict[str, Any]:
    try:
        topics = json.loads(_value(row, "topics_json", "[]") or "[]")
    except (TypeError, json.JSONDecodeError):
        topics = []
    summary = str(
        _value(row, "summary", "")
        or _value(row, "content", "")
        or _value(row, "raw_text", "")
        or ""
    ).strip()
    item = {
        "title": str(_value(row, "title", "未命名条目")),
        "url": str(_value(row, "url", "") or _value(row, "source_url", "") or ""),
        "source": str(_value(row, "source_name", "未知来源")),
        "group": str(_value(row, "source_group", source.get("group", "未分组"))),
        "source_type": str(source.get("source_type", "primary")),
        "authority": _bounded_float(source.get("authority", 0.75), 0.75),
        "reachability": _bounded_float(source.get("reachability", 0.45), 0.45),
        "locality": str(source.get("locality", "") or ""),
        "source_sections": _source_sections(source),
        "summary": summary[:1200],
        "reason": str(_value(row, "reason", "") or "")[:500],
        "action": str(_value(row, "action", "") or "")[:500],
        "topics": topics,
        "topics_text": " ".join(str(topic) for topic in topics),
        "importance": _bounded_float(_value(row, "importance", 0.0)),
        "relevance": _bounded_float(_value(row, "relevance", 0.0)),
        "novelty": _bounded_float(_value(row, "novelty", 0.0)),
        "time_sensitive": bool(_value(row, "time_sensitive", False)),
        "publish_date": _value(row, "publish_date"),
        "deadline": _value(row, "deadline"),
        "first_seen_at": _value(row, "first_seen_at"),
        "changed_at": _value(row, "changed_at"),
    }
    item["sections"] = _matched_sections(item)
    item["score"] = _item_score(item)
    return item


def _dedupe(items: list[dict]) -> list[dict]:
    best: dict[str, dict] = {}
    for item in items:
        key = item.get("url") or _normalize_title(item.get("title", ""))
        if not key:
            continue
        current = best.get(key)
        if current is None or item["score"] > current["score"]:
            best[key] = item
    return list(best.values())


def _public_item(item: dict) -> dict:
    summary = (item.get("summary") or item.get("reason") or "").strip()
    why = (item.get("reason") or "").strip()
    return {
        "title": item.get("title") or "未命名条目",
        "summary": summary[:420],
        "why": why[:220],
        "action": (item.get("action") or "")[:220],
        "source": item.get("source") or "未知来源",
        "url": item.get("url") or "",
        "publish_date": item.get("publish_date"),
        "deadline": item.get("deadline"),
        "locality": item.get("locality") or "",
        "reachability": item.get("reachability", 0.45),
        "score": item.get("score", 0.0),
    }


def _diverse_front(items: list[dict], limit: int) -> list[dict]:
    selected: list[dict] = []
    source_counts: dict[str, int] = {}
    represented_sections: set[str] = set()
    ranked = sorted(items, key=lambda item: item["score"], reverse=True)

    # Guarantee that a genuinely actionable opportunity gets front-page space when available.
    actionable = [
        item for item in ranked
        if "opportunity" in item.get("sections", []) and item.get("reachability", 0.0) >= 0.75
    ]
    if actionable and limit > 0:
        first = actionable[0]
        selected.append(first)
        source = first.get("source") or ""
        source_counts[source] = 1
        represented_sections.update(first.get("sections", []))

    # Reward topical diversity and prevent one prolific source from taking the front page.
    for item in ranked:
        if len(selected) >= limit:
            break
        if item in selected:
            continue
        source = item.get("source") or ""
        if source_counts.get(source, 0) >= 2:
            continue
        new_section = next((section for section in item.get("sections", []) if section not in represented_sections), None)
        if new_section or len(selected) < 3:
            selected.append(item)
            source_counts[source] = source_counts.get(source, 0) + 1
            represented_sections.update(item.get("sections", []))

    selected_keys = {item.get("url") or _normalize_title(item.get("title", "")) for item in selected}
    for item in ranked:
        if len(selected) >= limit:
            break
        key = item.get("url") or _normalize_title(item.get("title", ""))
        if key in selected_keys or item["score"] < 0.50:
            continue
        source = item.get("source") or ""
        if source_counts.get(source, 0) >= 2:
            continue
        selected.append(item)
        selected_keys.add(key)
        source_counts[source] = source_counts.get(source, 0) + 1
    return selected


def _fallback_newspaper(items: list[dict], report_date: str, reason: str) -> dict:
    ranked = sorted(_dedupe(items), key=lambda item: item["score"], reverse=True)
    page_map: dict[str, list[dict]] = {}

    front_limit = next(section["limit"] for section in SECTION_DEFS if section["id"] == "front")
    page_map["front"] = _diverse_front(ranked, front_limit)

    for section in SECTION_DEFS:
        if section["id"] == "front":
            continue
        candidates = [item for item in ranked if section["id"] in item.get("sections", [])]
        if section["id"] == "opportunity":
            candidates.sort(key=lambda item: (item.get("reachability", 0.0), item["score"]), reverse=True)
        page_map[section["id"]] = candidates[: section["limit"]]

    pages = []
    for section in SECTION_DEFS:
        selected = page_map.get(section["id"], [])
        lead = selected[0] if selected else None
        pages.append(
            {
                "id": section["id"],
                "title": section["title"],
                "subtitle": section["subtitle"],
                "headline": (lead or {}).get("title", ""),
                "overview": (
                    f"本版筛出 {len(selected)} 个高信号事件。"
                    if selected
                    else "今日没有足够重要、相关且可靠的更新需要占用这一版。"
                ),
                "items": [_public_item(item) for item in selected],
            }
        )

    return {
        "edition": "OR Morning",
        "report_date": report_date,
        "pages": pages,
        "llm": {"used": False, "model": None, "reason": reason, "input_items": len(items)},
    }


def _normalize_llm_pages(data: dict, fallback: dict, report_date: str) -> dict:
    raw_pages = data.get("pages") if isinstance(data, dict) else None
    if not isinstance(raw_pages, list):
        return fallback

    fallback_by_id = {page["id"]: page for page in fallback["pages"]}
    raw_by_id = {str(page.get("id")): page for page in raw_pages if isinstance(page, dict)}
    pages = []

    for section in SECTION_DEFS:
        raw = raw_by_id.get(section["id"], {})
        fallback_page = fallback_by_id[section["id"]]
        raw_items = raw.get("items") if isinstance(raw.get("items"), list) else []
        items = []
        for item in raw_items[: section["limit"]]:
            if not isinstance(item, dict) or not str(item.get("title") or "").strip():
                continue
            items.append(
                {
                    "title": str(item.get("title") or "")[:240],
                    "summary": str(item.get("summary") or "")[:520],
                    "why": str(item.get("why") or "")[:260],
                    "action": str(item.get("action") or "")[:260],
                    "source": str(item.get("source") or "未知来源")[:160],
                    "url": str(item.get("url") or "")[:2000],
                    "publish_date": item.get("publish_date"),
                    "deadline": item.get("deadline"),
                    "locality": str(item.get("locality") or "")[:120],
                }
            )
        pages.append(
            {
                "id": section["id"],
                "title": str(raw.get("title") or section["title"])[:120],
                "subtitle": str(raw.get("subtitle") or section["subtitle"])[:240],
                "headline": str(raw.get("headline") or fallback_page.get("headline") or "")[:260],
                "overview": str(raw.get("overview") or fallback_page.get("overview") or "")[:700],
                "items": items if raw_items else fallback_page["items"],
            }
        )

    return {
        "edition": str(data.get("edition") or "OR Morning")[:80],
        "report_date": report_date,
        "pages": pages,
    }


def build_newspaper(rows, sources: list[dict], report_date: str, profile: dict | None = None) -> dict:
    """Edit the rolling high-signal pool into the eight fixed OR Morning sections.

    The caller should pass the current edition window (08:00 Beijing to next 08:00),
    not merely the items changed in the latest crawl. This lets an hourly refresh keep
    the morning's important stories instead of forgetting them on every run.
    """
    sources_by_name = _source_meta(sources)
    items = [
        _editor_item(row, sources_by_name.get(str(_value(row, "source_name", "")), {}))
        for row in rows
    ]
    items = [item for item in items if item["score"] >= 0.40]
    fallback = _fallback_newspaper(items, report_date, "deterministic_editor")
    if not items:
        fallback["llm"]["reason"] = "no_selected_items"
        return fallback

    api_key, model, _ = _client_config()
    if not api_key:
        fallback["llm"]["reason"] = "missing_api_key"
        return fallback

    max_input = int((profile or {}).get("editorial_preferences", {}).get("max_editor_input_items", 64))
    ranked = sorted(_dedupe(items), key=lambda item: item["score"], reverse=True)[: max(8, max_input)]
    payload_items = [
        {
            "title": item["title"],
            "url": item["url"],
            "source": item["source"],
            "source_type": item["source_type"],
            "authority": item["authority"],
            "reachability": item["reachability"],
            "locality": item["locality"],
            "sections": item["sections"],
            "summary": item["summary"],
            "reason": item["reason"],
            "action": item["action"],
            "importance": item["importance"],
            "relevance": item["relevance"],
            "novelty": item["novelty"],
            "time_sensitive": item["time_sensitive"],
            "publish_date": item["publish_date"],
            "deadline": item["deadline"],
        }
        for item in ranked
    ]

    system_prompt = """你是 Opportunity Radar（OR Morning）的总编辑。输入是过去一个 edition window 中已经通过第一层过滤的高信号候选。你要把它们编辑成一份只服务于当前用户的八版个人时报。

固定版面（id 必须完全一致）：
front=今日总览；opportunity=机会雷达；research=科研前沿；ai=AI Frontier；math=数学×AI；engineering=Engineering；business=AI商业/产业；world=世界状态。

编辑规则：
1. front 只放全局最重要的 5-7 件事；其他版每版 0-6 件。没有足够重要内容时允许为空，绝不为了填版面降标准。
2. “机会雷达”是产品第一优先级。先问用户能不能在未来约 45 天内真实报名、申请、参赛、投稿、到场或建立联系，再问这个机会有多知名。优先北京线下、全国/线上、本科生/学生/个人开发者开放、参与成本低且可能产生项目/人脉/科研/简历结果的机会。
3. 输入中的 reachability 是可触达先验，locality 是地理/参与范围。高 reachability 的 Hackathon、竞赛、高校活动、科研招募、实习和 Workshop 不应被海外高级全职职位压过。海外 frontier 机会仍可保留，但若当前资格明显不匹配，只作为拓展信息。
4. AI/科研/数学/工程版仍优先真正改变认知或工作方法的 frontier AI、Agent、RL、Interpretability、AI for Mathematics、顶会变化和基础设施进展。
5. 同一事件的多来源报道要合并成一个 story；优先选择最权威、最接近一手的来源作为 source/url。二手报道不能压过一手公告。
6. summary 用中文写核心事实；why 用中文解释“为什么这件事值得这个用户占用注意力”；action 只有确实需要行动时才写，并尽量写清下一步。英文来源标题可保留必要专名，但整份日报以中文为主。
7. 标题要准确、短、信息密度高，不要标题党。只能使用输入事实，不得补充输入中不存在的数字、日期、结论或因果关系。
8. front 可以复用各专题版的最重要 story；如果存在高 reachability 的时效机会，front 至少应出现一条。专题版之间尽量减少无意义重复。
9. 输出中文 JSON，禁止 Markdown，禁止解释。

输出格式：
{"edition":"OR Morning","pages":[{"id":"front","title":"今日总览","subtitle":"","headline":"","overview":"","items":[{"title":"","summary":"","why":"","action":"","source":"","url":"","publish_date":null,"deadline":null,"locality":""}]}]}
必须输出八个 page。
"""

    try:
        data, actual_model = _post_json(
            system_prompt,
            {
                "date": report_date,
                "user_profile": _profile_text(profile),
                "sections": SECTION_DEFS,
                "items": payload_items,
            },
            timeout=180,
        )
        normalized = _normalize_llm_pages(data, fallback, report_date)
        normalized["llm"] = {
            "used": True,
            "model": actual_model,
            "input_items": len(payload_items),
            "available_items": len(items),
        }
        return normalized
    except Exception as exc:
        LOGGER.exception("DeepSeek newspaper editor failed")
        fallback["llm"] = {
            "used": False,
            "model": model,
            "reason": f"api_failed: {exc}",
            "input_items": len(payload_items),
        }
        return fallback
