from __future__ import annotations

from pathlib import Path


LATEX_REPLACEMENTS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def esc(value) -> str:
    text = str(value or "")
    return "".join(LATEX_REPLACEMENTS.get(ch, ch) for ch in text)


def _link(url: str) -> str:
    if not url:
        return ""
    # \url handles common URL punctuation more robustly than hand-escaping a
    # \href target. Keeping the URL visible is also useful in exported briefs.
    safe = url.replace("\\", "").replace("{", "%7B").replace("}", "%7D")
    return rf"\url{{{safe}}}"


def generate_latex(digest: dict, report_date: str, report_dir: str) -> Path:
    root = Path(report_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{report_date}.tex"

    parts = [
        r"\documentclass[11pt]{ctexart}",
        r"\usepackage[a4paper,margin=2.2cm]{geometry}",
        r"\usepackage{hyperref}",
        r"\usepackage{enumitem}",
        r"\setlist{nosep}",
        r"\hypersetup{colorlinks=true,urlcolor=blue}",
        r"\title{Opportunity Radar\\Daily Intelligence Brief}",
        rf"\date{{{esc(report_date)}}}",
        r"\begin{document}",
        r"\maketitle",
        rf"\begin{{quote}}\Large {esc(digest.get('headline') or '世界正在发生。')}\end{{quote}}",
        r"\section*{今日总览}",
        esc(digest.get("overview") or "今日没有需要占用注意力的新信息。"),
    ]

    for group in digest.get("groups") or []:
        parts += [
            rf"\section*{{{esc(group.get('name') or '未分组')}}}",
            esc(group.get("summary") or ""),
            r"\begin{itemize}",
        ]
        for item in group.get("highlights") or []:
            title = esc(item.get("title") or "未命名条目")
            source = esc(item.get("source") or "未知来源")
            raw_detail = "；".join(
                str(x)
                for x in [item.get("why") or "", item.get("action") or ""]
                if x
            )
            link = _link(str(item.get("url") or ""))
            parts.append(rf"\item \textbf{{{title}}}（{source}） {esc(raw_detail)} {link}")
        parts.append(r"\end{itemize}")

    signals = digest.get("cross_group_signals") or []
    if signals:
        parts += [r"\section*{跨组信号}", r"\begin{itemize}"]
        parts += [rf"\item {esc(signal)}" for signal in signals]
        parts.append(r"\end{itemize}")

    actions = digest.get("action_items") or []
    if actions:
        parts += [r"\section*{今日行动}", r"\begin{itemize}"]
        parts += [rf"\item {esc(action)}" for action in actions]
        parts.append(r"\end{itemize}")

    parts.append(r"\end{document}")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return path
