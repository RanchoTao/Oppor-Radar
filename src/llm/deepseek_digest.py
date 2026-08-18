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
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _row_to_item(row, source_meta: dict[str, dict]) -> dict[str, Any]:
    meta = source_meta.get(row["source_name"], {})
    return {
        "title": row["title"],
        "url": row["url"] or row["source_url"],
        "source": row["source_name"],
        "group": meta.get("group", "未分组"),
        "tags": meta.get("tags", []),
        "summary": (row["summary"] or row["raw_text"] or "")[:700],
        "publish_date": row["publish_date"],
        "deadline": row["deadline"],
        "event_date": row["event_date"],
        "location": row["location"],
    }


def _fallback_digest(items: list[dict[str, Any]], report_date: str, reason: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        grouped[item["group"]].append(item)

    groups = []
    for name, group_items in grouped.items():
        groups.append(
            {
                "name": name,
                "summary": f"今日发现 {len(group_items)} 条新信息，尚未经过大模型二次筛选。",
                "highlights": [
                    {
                        "title": item["title"],
                        "why": "来自你订阅的信息源的新条目。",
                        "action": "按需打开原文确认。",
                        "source": item["source"],
                        "url": item["url"],
                    }
                    for item in group_items[:8]
                ],
            }
        )

    return {
        "report_date": report_date,
        "headline": "世界正在发生；以下是今日新出现的信息。",
        "overview": f"共发现 {len(items)} 条新信息。{reason}",
        "groups": groups,
        "cross_group_signals": [],
        "action_items": [],
        "llm": {"used": False, "model": None, "reason": reason},
    }


def build_daily_digest(rows, sources: list[dict], report_date: str) -> dict[str, Any]:
    """Summarize newly discovered items with DeepSeek in one batched request.

    The crawler remains the acquisition layer. The LLM only receives extracted
    source snippets and is instructed to rank, compress and organize them without
    inventing facts. If no API key is configured, the pipeline still produces a
    deterministic fallback report so scheduled runs do not fail.
    """
    source_meta = {source["name"]: source for source in sources}
    items = [_row_to_item(row, source_meta) for row in rows]

    if not items:
        return {
            "report_date": report_date,
            "headline": "世界正在发生，但你的信息源今天没有发现新的条目。",
            "overview": "本次扫描没有发现相对于数据库而言的新链接。",
            "groups": [],
            "cross_group_signals": [],
            "action_items": [],
            "llm": {"used": False, "model": None, "reason": "no_new_items"},
        }

    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        return _fallback_digest(items, report_date, "未配置 DEEPSEEK_API_KEY，已使用规则化回退日报。")

    model = os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)
    base_url = os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    max_items = max(1, int(os.getenv("OPPOR_LLM_MAX_ITEMS", "120")))
    selected = items[:max_items]

    system_prompt = """你是 Opportunity Radar 的日报编辑器。你的任务不是只找夏令营或申请机会，而是把用户主动订阅的几十到上百个网页信息源压缩成一份个性化情报日报。信息源可能来自学术、金融、社会、科技、政策、个人博客或任何用户自定义分组。

严格要求：
1. 只能依据输入条目，不得补充输入中不存在的事实。
2. 先判断什么真正值得用户注意，再做压缩；不要机械逐条复述。
3. 保留跨来源、跨分组之间可能相关的信号，但只有证据充分时才指出。
4. 对每个重要条目说明“为什么值得看”和一个简短行动建议；没有行动必要时写“仅供了解”。
5. 输出中文。
6. 必须只输出一个 JSON 对象，不要 Markdown，不要代码围栏。

JSON 结构必须是：
{
  "headline": "一句话概括今天",
  "overview": "2-5 句总览",
  "groups": [
    {
      "name": "分组名",
      "summary": "该组概览",
      "highlights": [
        {"title":"", "why":"", "action":"", "source":"", "url":""}
      ]
    }
  ],
  "cross_group_signals": ["跨组信号"],
  "action_items": ["真正需要用户采取行动的事项"]
}
"""

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "date": report_date,
                        "instruction": "请从这些新条目中生成今天的个性化日报。优先级由信息本身的重要性、时效性、与来源分组的相关性共同决定。",
                        "items": selected,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "stream": False,
    }

    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=90,
        )
        response.raise_for_status()
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        digest = json.loads(_clean_json_text(content))
        digest["report_date"] = report_date
        digest["llm"] = {
            "used": True,
            "model": body.get("model") or model,
            "input_items": len(selected),
            "truncated": len(items) > len(selected),
        }
        return digest
    except Exception as exc:
        LOGGER.exception("DeepSeek daily digest failed")
        return _fallback_digest(items, report_date, f"DeepSeek 调用失败，已回退：{exc}")
