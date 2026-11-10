from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from typing import Any

import re
import time

import requests

from src.crawler.quality import is_low_signal_title

LOGGER = logging.getLogger(__name__)
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"

# Only concrete "something happened" verbs/nouns. Generic words such as "model",
# "research" or "new" matched almost every page and made the fallback keep ~98%.
HIGH_SIGNAL_TERMS = [
    "announc", "introducing", "releases", "released", "launch", "unveil", "open-source",
    "open source", "benchmark", "state-of-the-art", "breakthrough", "theorem", "proof",
    "call for", "deadline", "internship", "fellowship", "scholarship", "summer school",
    "hackathon", "competition", "contest", "发布", "推出", "开源", "突破", "定理", "证明",
    "征稿", "截止", "实习", "奖学金", "暑校", "黑客松", "竞赛", "挑战赛", "招募", "重磅",
]

OPPORTUNITY_TERMS = [
    "deadline", "cfp", "internship", "fellowship", "scholarship", "summer school", "winter school",
    "call for", "application", "apply", "residency", "hackathon", "competition", "contest", "meetup",
    "developer event", "招生", "报名", "截止", "实习", "奖学金", "招聘", "申请", "暑校", "访问",
    "资助", "黑客松", "竞赛", "比赛", "挑战赛", "活动", "招募", "科研训练", "本科生", "开发者",
]


def _interest_terms(profile: dict | None) -> list[str]:
    """Split long free-text interests ("AI Agent 与长期任务") into matchable terms."""
    terms: list[str] = []
    for interest in (profile or {}).get("interests", []):
        for part in re.split(r"[/、,，;；()（）与及和]|\s+and\s+", str(interest)):
            part = part.strip().lower()
            if not part:
                continue
            ascii_only = part.isascii()
            # Short ASCII tokens ("ai", "ml", "rl") match inside unrelated words.
            if (ascii_only and len(part) >= 4) or (not ascii_only and len(part) >= 2):
                terms.append(part)
    return list(dict.fromkeys(terms))


def _clean_json_text(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _client_config() -> tuple[str, str, str]:
    return (
        os.getenv("DEEPSEEK_API_KEY", "").strip(),
        os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
    )


def _post_json(
    system_prompt: str,
    user_payload: dict,
    timeout: int = 120,
    max_tokens: int = 8192,
    attempts: int = 2,
) -> tuple[dict, str]:
    """Call the chat API and parse a JSON object. Retries once on any failure."""
    api_key, model, base_url = _client_config()
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")

    last_error: Exception | None = None
    for attempt in range(max(1, attempts)):
        try:
            response = requests.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                    ],
                    "response_format": {"type": "json_object"},
                    "thinking": {"type": "disabled"},
                    "max_tokens": max_tokens,
                    "stream": False,
                },
                timeout=timeout,
            )
            response.raise_for_status()
            body = response.json()
            choice = body["choices"][0]
            if choice.get("finish_reason") == "length":
                raise ValueError("model output truncated (finish_reason=length)")
            content = choice["message"]["content"]
            return json.loads(_clean_json_text(content)), body.get("model") or model
        except Exception as exc:  # network, HTTP, truncation or JSON errors
            last_error = exc
            LOGGER.warning("DeepSeek call failed (attempt %s/%s): %s", attempt + 1, attempts, exc)
            if attempt + 1 < attempts:
                time.sleep(3)
    raise RuntimeError(f"DeepSeek call failed: {last_error}") from last_error


def _source_meta(sources: list[dict]) -> dict[str, dict]:
    return {source["name"]: source for source in sources}


def _profile_text(profile: dict | None) -> dict:
    profile = profile or {}
    return {
        "interests": profile.get("interests", []),
        "high_priority_signals": profile.get("high_priority_signals", []),
        "low_priority_signals": profile.get("low_priority_signals", []),
        "newspaper_sections": profile.get("newspaper_sections", []),
        "editorial_preferences": profile.get("editorial_preferences", {}),
    }


def _row_value(row, key: str, default=None):
    try:
        value = row[key]
    except (KeyError, IndexError, TypeError):
        return default
    return default if value is None else value


def _bounded(value, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _row_payload(row, sources_by_name: dict[str, dict], content_limit: int = 2500) -> dict[str, Any]:
    source = sources_by_name.get(_row_value(row, "source_name", ""), {})
    content = _row_value(row, "content", "") or _row_value(row, "raw_text", "") or _row_value(row, "summary", "") or ""
    return {
        "title": _row_value(row, "title", ""),
        "url": _row_value(row, "url", "") or _row_value(row, "source_url", ""),
        "source": _row_value(row, "source_name", ""),
        "group": _row_value(row, "source_group", source.get("group", "未分组")),
        "source_tags": source.get("tags", []),
        "source_watch": source.get("watch", []),
        "source_type": source.get("source_type", "primary"),
        "source_authority": _bounded(source.get("authority", 0.75), 0.75),
        "source_reachability": _bounded(source.get("reachability", 0.45), 0.45),
        "source_locality": source.get("locality", ""),
        "preferred_sections": source.get("sections", []),
        "publish_date": _row_value(row, "publish_date"),
        "deadline": _row_value(row, "deadline"),
        "event_date": _row_value(row, "event_date"),
        "location": _row_value(row, "location"),
        "content": str(content)[:content_limit],
    }


def _fallback_item_result(row, source: dict, profile: dict | None) -> dict:
    title = str(_row_value(row, "title", "") or "")
    text = str(_row_value(row, "summary", "") or _row_value(row, "content", "") or _row_value(row, "raw_text", "") or "")
    haystack = f" {title} {text[:1800]} ".lower()
    authority = _bounded(source.get("authority", 0.75), 0.75)
    reachability = _bounded(source.get("reachability", 0.45), 0.45)
    locality = str(source.get("locality", "") or "")
    source_sections = [str(x) for x in source.get("sections", []) if str(x)]
    tags = [str(x) for x in source.get("tags", []) if str(x)]

    # The source's own watch list is user-curated interest vocabulary too, and covers
    # English wording that the (mostly Chinese) profile phrases cannot match.
    watch_terms = [
        str(x).strip().lower()
        for x in source.get("watch", [])
        if len(str(x).strip()) >= (4 if str(x).isascii() else 2)
    ]
    interest_hits = sum(1 for term in dict.fromkeys(_interest_terms(profile) + watch_terms) if term in haystack)
    high_signal = any(term in haystack for term in HIGH_SIGNAL_TERMS)
    low_signal_title = is_low_signal_title(title)
    # A source being filed under "opportunity" is not evidence that this page is one.
    opportunity = any(term in haystack for term in OPPORTUNITY_TERMS)

    relevance = 0.40 + 0.09 * min(4, interest_hits) + 0.05 * min(3, len(source_sections))
    if opportunity:
        relevance += 0.22 * reachability
    relevance = min(0.98, relevance)
    importance = min(0.98, 0.34 + 0.48 * authority + (0.12 if high_signal else 0.0))
    novelty = 0.62 if high_signal else 0.48
    value = 0.40 * relevance + 0.32 * importance + 0.18 * novelty + (0.10 * reachability if opportunity else 0.0)

    # Without a model the fallback must be conservative: it needs positive evidence
    # that the page is about something the user cares about, not just a trusted source.
    keep = not low_signal_title and (
        (opportunity and reachability >= 0.6)
        or (interest_hits >= 1 and (high_signal or authority >= 0.85))
        or interest_hits >= 2
    )

    reason_parts = []
    if opportunity and reachability >= 0.75:
        reason_parts.append("这是当前用户可实际参与或申请的高可触达机会")
    if locality:
        reason_parts.append(f"参与范围：{locality}")
    if source_sections:
        reason_parts.append("命中用户订阅版面：" + "、".join(source_sections[:3]))
    if authority >= 0.9:
        reason_parts.append("来源接近一手且权威度高")
    if high_signal:
        reason_parts.append("标题/正文包含高信号变化")
    if interest_hits:
        reason_parts.append("与用户长期兴趣直接相关")
    reason = "；".join(reason_parts) or "来自用户主动订阅的信息源。"

    action = "仅供了解"
    if opportunity:
        action = "检查报名资格、截止时间、参与形式和预期收益；合适则立即加入任务系统。"

    summary = text.strip()[:1000] or title
    return {
        "url": _row_value(row, "url"),
        "title": title,
        "source": _row_value(row, "source_name", ""),
        "keep": keep,
        "summary": summary,
        "topics": list(dict.fromkeys(tags + source_sections))[:10],
        "importance": round(importance, 4),
        "relevance": round(relevance, 4),
        "novelty": round(novelty, 4),
        "reason": reason,
        "action": action,
        "time_sensitive": bool(_row_value(row, "deadline")) or opportunity,
    }


def rank_items(rows, sources: list[dict], profile: dict | None = None) -> tuple[list[dict], dict]:
    """Level 1: judge each new/changed item before it reaches the daily editor."""
    if not rows:
        return [], {"used": False, "reason": "no_items"}

    sources_by_name = _source_meta(sources)
    api_key, model, _ = _client_config()
    if not api_key:
        return [
            _fallback_item_result(row, sources_by_name.get(_row_value(row, "source_name", ""), {}), profile)
            for row in rows
        ], {"used": False, "reason": "missing_api_key", "model": None}

    system_prompt = """你是 Opportunity Radar 的第一层信息过滤器。用户主动订阅了大量高质量来源，你要判断每个新出现或发生变化的条目是否值得进入个人日报候选池。

输入包含正文、来源分组、来源类型、来源权威度、source_reachability（当前用户真实参与/申请的可触达程度）、source_locality（参与范围）、建议版面和用户兴趣画像。你不能因为来源权威就把所有页面保留；导航页、师资页、机构简介、重复常规更新仍应 keep=false。

规则：
1. 只能依据输入，不得虚构。
2. keep=false 用于导航、广告、重复常规内容、纯宣传、明显无关或信息量极低的条目。
3. 可行动机会优先：北京线下、全国/线上、本科生/学生/个人开发者开放的 Hackathon、竞赛、科研招募、实习、Workshop、Meetup、暑校与截止，应得到更高 relevance；明显不符合当前资格的海外资深岗位应降低 relevance。
4. 同时优先 frontier AI / Agent / RL / AI for Mathematics / 重要科研方法与顶会变化 / 真正有用的工程基础设施 / 足够重大的产业和政策变化。
5. importance/relevance/novelty 均为 0 到 1。不要把普通更新统一打高分。
6. summary 用中文压缩核心事实；reason 解释为什么值得当前用户占用注意力；英文专名可保留，但不要整段照搬英文网页。
7. action 没有必要行动时写“仅供了解”；有申请、截止、需要决策的机会时给具体下一步。
8. time_sensitive 只在存在截止、即将发生、价格/政策快速变化等明显时效性时为 true。
9. 宁缺毋滥。第一层应主动丢掉大量噪声。只返回 JSON。
10. 每条输入都必须有一条输出，id 与输入完全一致；不需要回填 url、title、source。

格式：
{"items":[{"id":0,"keep":false,"summary":"","topics":[],"importance":0.0,"relevance":0.0,"novelty":0.0,"reason":"","action":"","time_sensitive":false}]}
"""

    max_batch = max(1, int(os.getenv("OPPOR_LLM_ITEM_BATCH", "16")))
    results: list[dict] = []
    models: set[str] = set()
    failures: list[str] = []
    model_items = 0
    fallback_items = 0

    def fallback_for(row) -> dict:
        return _fallback_item_result(row, sources_by_name.get(_row_value(row, "source_name", ""), {}), profile)

    # Each batch succeeds or falls back on its own, and every row is matched back by a
    # numeric id we assign, not by the URL/title the model echoes (models normalise
    # URLs and rewrite titles, which used to leave rows unmatched and silently kept).
    for start in range(0, len(rows), max_batch):
        batch_rows = list(rows[start : start + max_batch])
        payload = []
        for offset, row in enumerate(batch_rows):
            item = _row_payload(row, sources_by_name)
            item["id"] = offset
            payload.append(item)
        try:
            data, actual_model = _post_json(
                system_prompt,
                {
                    "user_profile": _profile_text(profile),
                    "instruction": "逐条判断这些新信息是否值得进入今天的个人时报候选池。每条输入都必须输出一条结果，并原样返回它的 id。",
                    "items": payload,
                },
            )
            models.add(actual_model)
            by_id = {}
            for result in data.get("items") or []:
                if not isinstance(result, dict):
                    continue
                try:
                    by_id[int(result.get("id"))] = result
                except (TypeError, ValueError):
                    continue
        except Exception as exc:
            LOGGER.exception("DeepSeek item intelligence batch %s failed", start // max_batch)
            failures.append(str(exc)[:200])
            by_id = {}

        for offset, row in enumerate(batch_rows):
            result = by_id.get(offset)
            if result is None:
                results.append(fallback_for(row))
                fallback_items += 1
                continue
            merged = dict(result)
            # Identity always comes from our row, never from the model's echo.
            merged["url"] = _row_value(row, "url")
            merged["title"] = _row_value(row, "title", "")
            merged["source"] = _row_value(row, "source_name", "")
            merged["keep"] = bool(result.get("keep", False))
            for key in ("importance", "relevance", "novelty"):
                merged[key] = _bounded(result.get(key), 0.0)
            results.append(merged)
            model_items += 1

    meta = {
        "used": model_items > 0,
        "model": ", ".join(sorted(models)) or model,
        "input_items": len(rows),
        "model_items": model_items,
        "fallback_items": fallback_items,
    }
    if failures:
        meta["reason"] = "partial_api_failure" if model_items else f"api_failed: {failures[0]}"
        meta["failures"] = failures[:5]
    return results, meta


def _digest_item(row, source: dict) -> dict[str, Any]:
    try:
        topics = json.loads(_row_value(row, "topics_json", "[]") or "[]")
    except (TypeError, json.JSONDecodeError):
        topics = []
    return {
        "title": _row_value(row, "title", ""),
        "url": _row_value(row, "url", "") or _row_value(row, "source_url", ""),
        "source": _row_value(row, "source_name", ""),
        "group": _row_value(row, "source_group", source.get("group", "未分组")),
        "summary": _row_value(row, "summary", ""),
        "topics": topics,
        "importance": _bounded(_row_value(row, "importance", 0.0)),
        "relevance": _bounded(_row_value(row, "relevance", 0.0)),
        "novelty": _bounded(_row_value(row, "novelty", 0.0)),
        "reason": _row_value(row, "reason", ""),
        "action": _row_value(row, "action", ""),
        "time_sensitive": bool(_row_value(row, "time_sensitive", False)),
        "deadline": _row_value(row, "deadline"),
        "publish_date": _row_value(row, "publish_date"),
        "source_tags": source.get("tags", []),
        "reachability": _bounded(source.get("reachability", 0.45), 0.45),
        "locality": source.get("locality", ""),
    }


def _fallback_digest(items: list[dict], report_date: str, reason: str) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        grouped[item["group"]].append(item)

    groups = []
    for name, group_items in grouped.items():
        if name == "机会 / 本地与在线":
            group_items.sort(key=lambda x: (x.get("reachability", 0.0), x["relevance"], x["importance"]), reverse=True)
        else:
            group_items.sort(key=lambda x: (x["relevance"], x["importance"], x["novelty"]), reverse=True)
        groups.append(
            {
                "name": name,
                "summary": f"今日筛选出 {len(group_items)} 条值得关注的新信息。",
                "highlights": [
                    {
                        "title": item["title"],
                        "why": item.get("reason") or "来自用户订阅来源的新信息。",
                        "action": item.get("action") or "仅供了解",
                        "source": item["source"],
                        "url": item["url"],
                    }
                    for item in group_items[:8]
                ],
            }
        )

    groups.sort(key=lambda group: 0 if group["name"] == "机会 / 本地与在线" else 1)
    return {
        "report_date": report_date,
        "headline": "先看今天能行动的机会，再看世界发生了什么。",
        "overview": f"本次共有 {len(items)} 条信息进入日报。{reason}",
        "groups": groups,
        "cross_group_signals": [],
        "action_items": [
            item["action"]
            for item in items
            if item.get("time_sensitive") and item.get("action") and item["action"] != "仅供了解"
        ][:8],
        "llm": {"used": False, "model": None, "reason": reason},
    }


def build_daily_digest(rows, sources: list[dict], report_date: str, profile: dict | None = None) -> dict:
    """Compatibility digest used by Markdown/LaTeX and the legacy archive view."""
    sources_by_name = _source_meta(sources)
    items = [_digest_item(row, sources_by_name.get(_row_value(row, "source_name", ""), {})) for row in rows]
    if not items:
        return {
            "report_date": report_date,
            "headline": "世界正在发生，但今天没有足够重要的新信息需要占用你的注意力。",
            "overview": "订阅源已完成扫描；没有条目通过今日信息筛选。",
            "groups": [],
            "cross_group_signals": [],
            "action_items": [],
            "llm": {"used": False, "model": None, "reason": "no_selected_items"},
        }

    api_key, model, _ = _client_config()
    max_highlights = int((profile or {}).get("editorial_preferences", {}).get("max_daily_highlights", 24))
    items.sort(
        key=lambda x: (
            1 if x["group"] == "机会 / 本地与在线" else 0,
            x.get("reachability", 0.0),
            x["relevance"],
            x["importance"],
            x["novelty"],
        ),
        reverse=True,
    )
    selected = items[: max(1, max_highlights * 2)]

    if not api_key:
        return _fallback_digest(selected, report_date, "未配置大模型密钥，使用确定性回退编辑。")
    if os.getenv("OPPOR_LLM_LEGACY_DIGEST", "").strip().lower() not in {"1", "true", "yes"}:
        # The product page is the OR Morning newspaper (build_newspaper). This digest only
        # feeds the Markdown/LaTeX views, so it is not worth a second model call by default.
        return _fallback_digest(selected, report_date, "Markdown/LaTeX 兼容视图使用确定性编辑；网页时报由大模型编辑。")

    system_prompt = """你是 Opportunity Radar 的兼容日报编辑器。输入已经经过逐条筛选。你的任务是进一步压缩，而不是机械罗列。

要求：
1. 用中文写给一个高信息密度用户，不解释系统内部实现。
2. 优先真实可行动的机会：北京线下、全国/线上、本科生/学生/个人开发者开放；再保留真正重要、相关、时效强、跨来源互相印证的信息。
3. 明显不符合当前资格的海外高级岗位不能压过可报名的 Hackathon、竞赛、科研招募、实习、Workshop 与高校活动。
4. 同一事件多个来源应合并理解，避免重复占版面。
5. 如果不同分组之间存在可靠联系，写入 cross_group_signals；证据不足则不写。
6. action_items 只放确实需要用户行动的事项。
7. 只能依据输入，严禁补充未提供事实。只输出 JSON。

格式：
{"headline":"","overview":"","groups":[{"name":"","summary":"","highlights":[{"title":"","why":"","action":"","source":"","url":""}]}],"cross_group_signals":[],"action_items":[]}
"""

    try:
        data, actual_model = _post_json(
            system_prompt,
            {
                "date": report_date,
                "user_profile": _profile_text(profile),
                "max_highlights": max_highlights,
                "items": selected,
            },
        )
        data["report_date"] = report_date
        data["llm"] = {
            "used": True,
            "model": actual_model,
            "input_items": len(selected),
            "available_items": len(items),
        }
        return data
    except Exception as exc:
        LOGGER.exception("DeepSeek daily editor failed")
        return _fallback_digest(selected, report_date, f"日报编辑 API 调用失败，已回退：{exc}")
