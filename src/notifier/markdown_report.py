from __future__ import annotations

import json
from pathlib import Path

from src.notifier.latex_report import generate_latex


def _safe(value: str | None, fallback: str = "未提供") -> str:
    return value.strip() if isinstance(value, str) and value.strip() else fallback


def _row_json(row) -> dict:
    data = dict(row)
    try:
        data["topics"] = json.loads(data.pop("topics_json", "[]") or "[]")
    except (TypeError, json.JSONDecodeError):
        data["topics"] = []
    data["time_sensitive"] = bool(data.get("time_sensitive"))
    data["keep"] = bool(data.get("keep", 1))
    data["value_score"] = round(
        0.4 * float(data.get("relevance") or 0)
        + 0.35 * float(data.get("importance") or 0)
        + 0.25 * float(data.get("novelty") or 0),
        4,
    )
    return data


def generate_report(
    rows,
    report_date: str,
    report_dir: str = "data/reports",
    digest: dict | None = None,
    source_stats: dict | None = None,
) -> Path:
    """Write JSON as source-of-truth plus Markdown and LaTeX views."""
    report_root = Path(report_dir)
    report_root.mkdir(parents=True, exist_ok=True)
    md_path = report_root / f"{report_date}.md"
    json_path = report_root / f"{report_date}.json"

    digest = digest or {
        "headline": "世界正在发生。",
        "overview": "今日没有需要占用注意力的新信息。",
        "groups": [],
        "cross_group_signals": [],
        "action_items": [],
    }
    source_stats = source_stats or {}

    lines = [
        f"# Opportunity Radar · {report_date}",
        "",
        f"> {_safe(digest.get('headline'), '世界正在发生。')}",
        "",
        "## 今日总览",
        "",
        _safe(digest.get("overview"), "今日没有需要占用注意力的新信息。"),
        "",
    ]

    groups = digest.get("groups") or []
    for group in groups:
        lines += [
            f"## {_safe(group.get('name'), '未分组')}",
            "",
            _safe(group.get("summary"), ""),
            "",
        ]
        for item in group.get("highlights") or []:
            title = _safe(item.get("title"), "未命名条目")
            source = _safe(item.get("source"), "未知来源")
            url = item.get("url") or ""
            lines.append(f"### {title}")
            lines.append("")
            lines.append(f"**来源：** {source}")
            lines.append("")
            if item.get("why"):
                lines.append(f"**为什么值得看：** {item['why']}")
                lines.append("")
            if item.get("action") and item.get("action") != "仅供了解":
                lines.append(f"**建议：** {item['action']}")
                lines.append("")
            if url:
                lines.append(f"[查看原文]({url})")
                lines.append("")

    signals = digest.get("cross_group_signals") or []
    if signals:
        lines += ["## 跨领域信号", ""]
        lines += [f"- {signal}" for signal in signals]
        lines.append("")

    actions = digest.get("action_items") or []
    if actions:
        lines += ["## 今天值得做", ""]
        lines += [f"- [ ] {action}" for action in actions]
        lines.append("")

    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    generate_latex(digest, report_date, report_dir)

    metrics = {
        "configured_sources": int(source_stats.get("configured", 0)),
        "healthy_sources": int(source_stats.get("healthy", 0)),
        "new_items": int(source_stats.get("new_items", 0)),
        "changed_items": int(source_stats.get("changed_items", 0)),
        "candidate_items": int(source_stats.get("candidate_items", 0)),
        "selected_items": int(source_stats.get("selected_items", len(rows))),
        "last_updated_at": source_stats.get("last_updated_at"),
    }

    json_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "date": report_date,
                "metrics": metrics,
                "digest": {
                    key: value
                    for key, value in digest.items()
                    if key not in {"llm"}
                },
                "items": [_row_json(row) for row in rows],
                "diagnostics": {
                    "source_health": source_stats.get("source_health", []),
                    "item_intelligence": source_stats.get("item_intelligence", {}),
                    "daily_editor": digest.get("llm", {}),
                },
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    return md_path
