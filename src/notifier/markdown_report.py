from __future__ import annotations

import json
from pathlib import Path


def _safe(value: str | None, fallback: str = "未提供") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else fallback


def generate_report(
    rows,
    report_date: str,
    report_dir: str = "data/reports",
    digest: dict | None = None,
    source_stats: dict | None = None,
) -> Path:
    """Write both Markdown and structured JSON for the daily personalized brief."""
    report_root = Path(report_dir)
    report_root.mkdir(parents=True, exist_ok=True)
    md_path = report_root / f"{report_date}.md"
    json_path = report_root / f"{report_date}.json"

    digest = digest or {
        "headline": "今日信息摘要",
        "overview": f"共发现 {len(rows)} 条新信息。",
        "groups": [],
        "cross_group_signals": [],
        "action_items": [],
        "llm": {"used": False, "reason": "digest_not_provided"},
    }
    source_stats = source_stats or {}

    lines = [
        f"# Opportunity Radar · Daily Intelligence Brief · {report_date}",
        "",
        f"> {_safe(digest.get('headline'), '世界正在发生。')}",
        "",
        "## 今日总览",
        "",
        _safe(digest.get("overview"), "今日没有可汇总的新信息。"),
        "",
    ]

    groups = digest.get("groups") or []
    if groups:
        lines += ["## 分组情报", ""]
        for group in groups:
            lines += [f"### {_safe(group.get('name'), '未分组')}", "", _safe(group.get("summary"), "暂无摘要。"), ""]
            for item in group.get("highlights") or []:
                title = _safe(item.get("title"), "未命名条目")
                source = _safe(item.get("source"), "未知来源")
                url = item.get("url") or ""
                lines.append(f"- **{title}** · {source}")
                if item.get("why"):
                    lines.append(f"  - 为什么值得看：{item['why']}")
                if item.get("action"):
                    lines.append(f"  - 建议：{item['action']}")
                if url:
                    lines.append(f"  - 原文：{url}")
            lines.append("")

    signals = digest.get("cross_group_signals") or []
    if signals:
        lines += ["## 跨组信号", ""]
        lines += [f"- {signal}" for signal in signals]
        lines.append("")

    actions = digest.get("action_items") or []
    if actions:
        lines += ["## 今日行动", ""]
        lines += [f"- {action}" for action in actions]
        lines.append("")

    lines += ["## 新增条目索引", "", f"本次数据库首次发现 **{len(rows)}** 条链接。", ""]
    for row in rows:
        lines += [
            f"- [{row['title']}]({row['url'] or row['source_url']}) · {row['source_name']}",
        ]
    lines.append("")

    llm = digest.get("llm") or {}
    scanned = source_stats.get("scanned", 0)
    failed = source_stats.get("failed", 0)
    lines += [
        "## 系统状态",
        "",
        f"- 信息源扫描：{scanned} 成功 / {failed} 失败",
        f"- 大模型：{'已启用' if llm.get('used') else '未启用或已回退'}",
        f"- 模型：{llm.get('model') or '—'}",
        "",
    ]

    md_path.write_text("\n".join(lines), encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {
                "date": report_date,
                "digest": digest,
                "source_stats": source_stats,
                "new_items": [dict(row) for row in rows],
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    return md_path
