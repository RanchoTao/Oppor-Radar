from __future__ import annotations

from pathlib import Path

LABELS = {"A": "A类：必须申请", "B": "B类：值得申请", "C": "C类：可围观", "X": "X类：不适合/已过期"}


def generate_report(rows, report_date: str, report_dir: str = "data/reports") -> Path:
    Path(report_dir).mkdir(parents=True, exist_ok=True)
    path = Path(report_dir) / f"{report_date}.md"
    counts = {k: 0 for k in LABELS}
    for row in rows:
        counts[row["category"]] = counts.get(row["category"], 0) + 1
    lines = [
        f"# Opportunity Radar Daily Report - {report_date}", "", "## Summary", "",
        f"- New opportunities found: {len(rows)}",
        f"- A-class: {counts.get('A', 0)}",
        f"- B-class: {counts.get('B', 0)}",
        f"- C-class: {counts.get('C', 0)}",
        f"- X-class: {counts.get('X', 0)}", "",
    ]
    for cat, label in LABELS.items():
        lines += [f"## {label}", ""]
        cat_rows = [r for r in rows if r["category"] == cat]
        if not cat_rows:
            lines += ["暂无。", ""]
            continue
        for r in cat_rows:
            lines += [
                f"### {r['title']}",
                f"- 来源：{r['source_name']}",
                f"- 截止日期：{r['deadline'] or '未解析'}",
                f"- 活动时间：{r['event_date'] or '未解析'}",
                f"- 地点：{r['location'] or '未解析'}",
                f"- 分数：{r['score']}",
                f"- 推荐理由：{_reason(r)}",
                f"- 链接：{r['url'] or r['source_url']}", "",
            ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _reason(row) -> str:
    if row["category"] == "A":
        return "高相关度，建议优先查看并准备申请。"
    if row["category"] == "B":
        return "相关度较高，值得进一步确认要求。"
    if row["category"] == "C":
        return "有一定相关性，可作为信息储备。"
    return "相关性较低、招聘限制或可能已过期。"
