from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from typing import Any

import requests

LOGGER = logging.getLogger(__name__)
DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-flash"


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


def _post_json(system_prompt: str, user_payload: dict, timeout: int = 120) -> tuple[dict, str]:
    api_key, model, base_url = _client_config()
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")

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
            "stream": False,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    body = response.json()
    content = body["choices"][0]["message"]["content"]
    return json.loads(_clean_json_text(content)), body.get("model") or model


def _source_meta(sources: list[dict]) -> dict[str, dict]:
    return {source["name"]: source for source in sources}


def _profile_text(profile: dict | None) -> dict:
    profile = profile or {}
    return {
        "interests": profile.get("interests", []),
        "high_priority_signals": profile.get("high_priority_signals", []),
        "low_priority_signals": profile.get("low_priority_signals", []),
        "editorial_preferences": profile.get("editorial_preferences", {}),
    }


def _row_payload(row, sources_by_name: dict[str, dict], content_limit: int = 7000) -> dict[str, Any]:
    source = sources_by_name.get(row["source_name"], {})
    content = row["content"] or row["raw_text"] or row["summary"] or ""
    return {
        "title": row["title"],
        "url": row["url"] or row["source_url"],
        "source": row["source_name"],
        "group": row["source_group"] if "source_group" in row.keys() else source.get("group", "未分组"),
        "source_tags": source.get("tags", []),
        "source_watch": source.get("watch", []),
        "publish_date": row["publish_date"],
        "deadline": row["deadline"],
        "event_date": row["event_date"],
        "location": row["location"],
        "content": content[:content_limit],
    }


def _fallback_item_result(row, source: dict, profile: dict | None) -> dict:
    text = (row["summary"] or row["content"] or row["raw_text"] or "")[:1000]
    tags = list(source.get("tags", []))[:6]
    return {
        "url": row["url"],
        "title": row["title"],
        "source": row["source_name"],
        "keep": True,
        "summary": text,
        "topics": tags,
        "importance": 0.5,
        "relevance": 0.5,
        "novelty": 0.5,
        "reason": "来自用户主动订阅的信息源，等待大模型进一步判断。",
        "action": "仅供了解",
        "time_sensitive": bool(row["deadline"]),
    }


def rank_items(rows, sources: list[dict], profile: dict | None = None) -> tuple[list[dict], dict]:
    """Level 1: judge each new/changed item before it reaches the daily editor."""
    if not rows:
        return [], {"used": False, "reason": "no_items"}

    sources_by_name = _source_meta(sources)
    api_key, model, _ = _client_config()
    if not api_key:
        return [
            _fallback_item_result(row, sources_by_name.get(row["source_name"], {}), profile)
            for row in rows
        ], {"used": False, "reason": "missing_api_key", "model": None}

    system_prompt = """你是 Opportunity Radar 的第一层信息过滤器。用户主动订阅了大量网页来源，你要判断每个新出现或发生变化的条目是否值得进入个人日报。

你必须根据“输入正文 + 来源分组 + 用户兴趣画像”判断，而不是把所有条目都保留。不要把产品限定为申请/夏令营场景。

规则：
1. 只能依据输入，不得虚构。
2. keep=false 用于导航、广告、重复常规内容、明显无关内容或信息量极低的条目。
3. importance/relevance/novelty 均为 0 到 1 的数值。
4. summary 用中文压缩核心事实，不写空泛评价。
5. reason 说明为什么值得用户看；action 没有必要行动时写“仅供了解”。
6. time_sensitive 只在存在截止、即将发生、价格/政策快速变化等明显时效性时为 true。
7. 只返回 JSON。

格式：
{"items":[{"url":"","title":"","source":"","keep":true,"summary":"","topics":[],"importance":0.0,"relevance":0.0,"novelty":0.0,"reason":"","action":"","time_sensitive":false}]}
"""

    max_batch = max(1, int(os.getenv("OPPOR_LLM_ITEM_BATCH", "32")))
    results: list[dict] = []
    models: set[str] = set()
    payload_items = [_row_payload(row, sources_by_name) for row in rows]

    try:
        for start in range(0, len(payload_items), max_batch):
            batch = payload_items[start : start + max_batch]
            data, actual_model = _post_json(
                system_prompt,
                {
                    "user_profile": _profile_text(profile),
                    "instruction": "逐条判断这些新信息是否值得进入今天的个人日报。",
                    "items": batch,
                },
            )
            models.add(actual_model)
            results.extend(data.get("items") or [])
        return results, {"used": True, "model": ", ".join(sorted(models)) or model, "input_items": len(rows)}
    except Exception as exc:
        LOGGER.exception("DeepSeek item intelligence failed")
        return [
            _fallback_item_result(row, sources_by_name.get(row["source_name"], {}), profile)
            for row in rows
        ], {"used": False, "reason": f"api_failed: {exc}", "model": model}


def _digest_item(row, source: dict) -> dict[str, Any]:
    try:
        topics = json.loads(row["topics_json"] or "[]")
    except (TypeError, json.JSONDecodeError):
        topics = []
    return {
        "title": row["title"],
        "url": row["url"] or row["source_url"],
        "source": row["source_name"],
        "group": row["source_group"],
        "summary": row["summary"],
        "topics": topics,
        "importance": row["importance"],
        "relevance": row["relevance"],
        "novelty": row["novelty"],
        "reason": row["reason"],
        "action": row["action"],
        "time_sensitive": bool(row["time_sensitive"]),
        "deadline": row["deadline"],
        "publish_date": row["publish_date"],
        "source_tags": source.get("tags", []),
    }


def _fallback_digest(items: list[dict], report_date: str, reason: str) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        grouped[item["group"]].append(item)

    groups = []
    for name, group_items in grouped.items():
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

    return {
        "report_date": report_date,
        "headline": "世界正在发生；这是今天与你最相关的变化。",
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
    """Level 2: edit already-filtered information into one coherent daily brief."""
    sources_by_name = _source_meta(sources)
    items = [_digest_item(row, sources_by_name.get(row["source_name"], {})) for row in rows]
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
    items.sort(key=lambda x: (x["relevance"], x["importance"], x["novelty"]), reverse=True)
    selected = items[: max(1, max_highlights * 2)]

    if not api_key:
        return _fallback_digest(selected, report_date, "未配置大模型密钥，使用确定性回退编辑。")

    system_prompt = """你是 Opportunity Radar 的第二层日报主编。输入已经经过逐条筛选。你的任务是进一步压缩，而不是机械罗列。

要求：
1. 用中文写给一个高信息密度用户，不解释系统内部实现。
2. 优先保留真正重要、相关、时效强、跨来源互相印证的信息。
3. 同一事件多个来源应合并理解，避免重复占版面。
4. 如果不同分组之间存在可靠联系，写入 cross_group_signals；证据不足则不写。
5. action_items 只放确实需要用户行动的事项。
6. 只能依据输入，严禁补充未提供事实。
7. 只输出 JSON。

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
