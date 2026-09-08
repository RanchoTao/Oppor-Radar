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
    safe = url.replace("\\", "").replace("{", "%7B").replace("}", "%7D")
    return rf"\url{{{safe}}}"


def _base_preamble(report_date: str) -> list[str]:
    return [
        r"\documentclass[10.5pt]{ctexart}",
        r"\usepackage[a4paper,top=1.45cm,bottom=1.45cm,left=1.55cm,right=1.55cm]{geometry}",
        r"\usepackage{hyperref}",
        r"\usepackage{enumitem}",
        r"\usepackage{multicol}",
        r"\usepackage{titlesec}",
        r"\usepackage{xcolor}",
        r"\usepackage{fancyhdr}",
        r"\setlength{\parindent}{0pt}",
        r"\setlength{\parskip}{4pt}",
        r"\setlist{nosep,leftmargin=1.3em}",
        r"\definecolor{ormuted}{HTML}{626262}",
        r"\definecolor{orline}{HTML}{B9B5AE}",
        r"\hypersetup{colorlinks=true,urlcolor=black,linkcolor=black}",
        r"\pagestyle{fancy}",
        r"\fancyhf{}",
        rf"\lhead{{\small Opportunity Radar · OR Morning · {esc(report_date)}}}",
        r"\rhead{\small\thepage/8}",
        r"\cfoot{}",
        r"\renewcommand{\headrulewidth}{0.35pt}",
        r"\titleformat{\section}{\Huge\bfseries}{ }{0pt}{}",
        r"\begin{document}",
    ]


def _story(item: dict, lead: bool = False) -> list[str]:
    title = esc(item.get("title") or "未命名条目")
    summary = esc(item.get("summary") or item.get("why") or "")
    why = esc(item.get("why") or "")
    action = esc(item.get("action") or "")
    source = esc(item.get("source") or "未知来源")
    link = _link(str(item.get("url") or ""))
    heading = r"\Large\bfseries" if lead else r"\large\bfseries"
    parts = [rf"{{{heading} {title}}}\par"]
    if summary:
        parts.append(summary)
    if why and why != summary:
        parts.append(rf"\textbf{{与你有关：}} {why}")
    if action and action != "仅供了解":
        parts.append(rf"\textbf{{建议：}} {action}")
    source_line = rf"{{\footnotesize\color{{ormuted}} 来源：{source}"
    if link:
        source_line += rf" · {link}"
    source_line += "}"
    parts.append(source_line)
    return parts


def _page_header(page: dict, page_no: int, report_date: str) -> list[str]:
    subtitle = esc(page.get("subtitle") or "")
    return [
        rf"{{\small\bfseries OR MORNING / SECTION {page_no:02d} / {esc(report_date)}}}",
        r"\vspace{2mm}",
        r"\hrule height 0.9pt",
        r"\vspace{1.5mm}",
        r"\hrule height 0.25pt",
        r"\vspace{4mm}",
        rf"\section*{{{esc(page.get('title') or '未命名版面')}}}",
        rf"{{\color{{ormuted}} {subtitle}}}",
        r"\vspace{2mm}",
    ]


def _newspaper_latex(newspaper: dict, report_date: str) -> list[str]:
    pages = newspaper.get("pages") or []
    parts = _base_preamble(report_date)

    for page_no in range(1, 9):
        page = pages[page_no - 1] if page_no - 1 < len(pages) else {
            "title": f"第 {page_no} 版",
            "subtitle": "今日无重大更新。",
            "items": [],
        }
        if page_no > 1:
            parts.append(r"\newpage")
        parts.extend(_page_header(page, page_no, report_date))

        items = page.get("items") or []
        headline = esc(page.get("headline") or "")
        overview = esc(page.get("overview") or "")

        if page_no == 1:
            if headline:
                parts += [rf"{{\fontsize{{25}}{{29}}\selectfont\bfseries {headline}}}\par", r"\vspace{2mm}"]
            if overview:
                parts += [rf"{{\large {overview}}}", r"\vspace{3mm}"]
            if items:
                lead = items[0]
                parts.extend(_story(lead, lead=True))
                remaining = items[1:]
                if remaining:
                    parts += [r"\vspace{3mm}", r"\hrule height 0.25pt", r"\vspace{3mm}", r"\begin{multicols}{2}"]
                    for idx, item in enumerate(remaining):
                        parts.extend(_story(item))
                        if idx != len(remaining) - 1:
                            parts += [r"\vspace{2mm}", r"\hrule height 0.2pt", r"\vspace{2mm}"]
                    parts.append(r"\end{multicols}")
            else:
                parts.append(r"\vfill\begin{center}\Large 今日没有足够重要的新信息需要占用你的注意力。\end{center}\vfill")
        else:
            if headline:
                parts += [rf"{{\LARGE\bfseries {headline}}}\par", r"\vspace{1mm}"]
            if overview:
                parts += [rf"{{\color{{ormuted}} {overview}}}", r"\vspace{3mm}"]
            if items:
                parts.extend(_story(items[0], lead=True))
                remaining = items[1:]
                if remaining:
                    parts += [r"\vspace{4mm}", r"\hrule height 0.25pt", r"\vspace{3mm}", r"\begin{multicols}{2}"]
                    for idx, item in enumerate(remaining):
                        parts.extend(_story(item))
                        if idx != len(remaining) - 1:
                            parts += [r"\vspace{2mm}", r"\hrule height 0.2pt", r"\vspace{2mm}"]
                    parts.append(r"\end{multicols}")
            else:
                parts.append(r"\vfill\begin{center}\Large 今日无重大更新。\\[2mm]\normalsize 宁缺毋滥，不以低价值内容填充版面。\end{center}\vfill")

    parts.append(r"\end{document}")
    return parts


def _legacy_latex(digest: dict, report_date: str) -> list[str]:
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

    parts.append(r"\end{document}")
    return parts


def generate_latex(
    digest: dict,
    report_date: str,
    report_dir: str,
    newspaper: dict | None = None,
) -> Path:
    root = Path(report_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{report_date}.tex"
    parts = _newspaper_latex(newspaper, report_date) if newspaper and newspaper.get("pages") else _legacy_latex(digest, report_date)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return path
