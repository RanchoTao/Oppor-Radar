from __future__ import annotations

import html
import logging
import os
import smtplib
from email.message import EmailMessage

LOGGER = logging.getLogger(__name__)


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _dedupe(items: list[dict], limit: int = 8) -> list[dict]:
    selected: list[dict] = []
    seen: set[str] = set()
    for item in items:
        key = str(item.get("url") or item.get("title") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        selected.append(item)
        if len(selected) >= limit:
            break
    return selected


def _action_items(newspaper: dict) -> list[dict]:
    pages = newspaper.get("pages") if isinstance(newspaper, dict) else []
    pages = pages if isinstance(pages, list) else []
    by_id = {str(page.get("id")): page for page in pages if isinstance(page, dict)}

    # Actionable opportunities come first; front-page intelligence fills the remainder.
    candidates: list[dict] = []
    for page_id in ("opportunity", "front"):
        page = by_id.get(page_id) or {}
        items = page.get("items") if isinstance(page.get("items"), list) else []
        candidates.extend(item for item in items if isinstance(item, dict))
    return _dedupe(candidates, limit=8)


def _plain_body(items: list[dict], report_date: str, public_url: str) -> str:
    lines = [f"OR Morning · {report_date}", "", "今天最值得你行动/关注的事项：", ""]
    if not items:
        lines.append("今天没有足够高信号的可行动事项。")
    for index, item in enumerate(items, 1):
        lines.append(f"{index}. {item.get('title') or '未命名条目'}")
        summary = str(item.get("summary") or item.get("why") or "").strip()
        action = str(item.get("action") or "").strip()
        if summary:
            lines.append(f"   {summary}")
        if action and action != "仅供了解":
            lines.append(f"   行动：{action}")
        if item.get("url"):
            lines.append(f"   {item['url']}")
        lines.append("")
    lines.extend(["完整日报：", public_url])
    return "\n".join(lines)


def _html_body(items: list[dict], report_date: str, public_url: str) -> str:
    cards = []
    for index, item in enumerate(items, 1):
        title = html.escape(str(item.get("title") or "未命名条目"))
        summary = html.escape(str(item.get("summary") or item.get("why") or "").strip())
        action = html.escape(str(item.get("action") or "").strip())
        url = html.escape(str(item.get("url") or ""), quote=True)
        parts = [f"<h3 style='margin:0 0 6px;font-size:17px'>{index}. {title}</h3>"]
        if summary:
            parts.append(f"<p style='margin:0 0 7px;line-height:1.65;color:#333'>{summary}</p>")
        if action and action != "仅供了解":
            parts.append(f"<p style='margin:0 0 7px;line-height:1.55'><strong>行动：</strong>{action}</p>")
        if url:
            parts.append(f"<a href='{url}' style='color:#173b5e'>查看原文</a>")
        cards.append("<div style='padding:14px 0;border-top:1px solid #ddd'>" + "".join(parts) + "</div>")

    if not cards:
        cards.append("<p>今天没有足够高信号的可行动事项。</p>")

    safe_url = html.escape(public_url, quote=True)
    return (
        "<div style='max-width:680px;margin:auto;font-family:system-ui,-apple-system,Segoe UI,sans-serif;color:#111'>"
        f"<p style='font-size:12px;letter-spacing:.08em;color:#666'>OPPORTUNITY RADAR · {html.escape(report_date)}</p>"
        "<h1 style='margin:0 0 6px;font-size:30px'>今天值得行动的机会</h1>"
        "<p style='margin:0 0 18px;color:#666'>优先展示你能真正报名、参加、申请或接触到的机会。</p>"
        + "".join(cards)
        + f"<p style='margin-top:22px'><a href='{safe_url}' style='color:#173b5e;font-weight:700'>打开完整 OR Morning →</a></p>"
        "</div>"
    )


def send_daily_email(newspaper: dict, report_date: str) -> dict:
    """Send the daily OR email when SMTP credentials are configured.

    Missing credentials are intentionally non-fatal so local runs and GitHub Actions can
    continue generating the newspaper before email delivery is configured.
    """
    if not _truthy(os.getenv("OR_EMAIL_ENABLED", "false")):
        return {"sent": False, "reason": "disabled"}

    username = os.getenv("OR_SMTP_USERNAME", "").strip()
    password = os.getenv("OR_SMTP_PASSWORD", "").strip()
    recipient = os.getenv("OR_EMAIL_TO", "").strip() or username
    sender = os.getenv("OR_EMAIL_FROM", "").strip() or username
    host = os.getenv("OR_SMTP_HOST", "smtp.gmail.com").strip() or "smtp.gmail.com"
    port = int(os.getenv("OR_SMTP_PORT", "465"))
    public_url = os.getenv("OR_PUBLIC_URL", "https://ranchotao.com/Oppor-Radar/").strip()

    if not username or not password or not recipient or not sender:
        LOGGER.warning("OR email delivery skipped: SMTP credentials/recipient are not configured")
        return {"sent": False, "reason": "missing_smtp_credentials"}

    items = _action_items(newspaper)
    message = EmailMessage()
    message["Subject"] = f"OR Morning · {report_date} · 今日值得行动"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(_plain_body(items, report_date, public_url))
    message.add_alternative(_html_body(items, report_date, public_url), subtype="html")

    try:
        with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
            smtp.login(username, password)
            smtp.send_message(message)
        LOGGER.info("OR Morning email sent to %s", recipient)
        return {"sent": True, "recipient": recipient, "items": len(items)}
    except Exception as exc:
        LOGGER.exception("OR email delivery failed")
        return {"sent": False, "reason": f"smtp_failed: {exc}"}
