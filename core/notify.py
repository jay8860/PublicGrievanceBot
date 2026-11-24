"""Telegram notifications sent by the backend (assignment, reminder, escalation).

The bot is only the transport: every send is recorded in ``notifications`` with
an optional dedupe key, so a retrying worker can never spam an officer twice
for the same event.
"""
import logging
from typing import Optional

import requests
from sqlalchemy.orm import Session

from config import get_env

from .models import Complaint, Notification, Officer

logger = logging.getLogger(__name__)

BOT_TOKEN = get_env("TELEGRAM_BOT_TOKEN")
API_BASE = "https://api.telegram.org"
TIMEOUT = 15


def _log(db: Session, *, complaint_id: Optional[str], chat_id: str, kind: str,
         status: str, dedupe_key: Optional[str], error: str = "") -> None:
    db.add(Notification(complaint_id=complaint_id, chat_id=str(chat_id), kind=kind,
                        status=status, dedupe_key=dedupe_key, error=error[:400]))


def already_sent(db: Session, dedupe_key: str) -> bool:
    return db.query(Notification.id).filter(Notification.dedupe_key == dedupe_key).first() is not None


def send(db: Session, *, chat_id, text: str, kind: str = "message",
         complaint_id: Optional[str] = None, photo_file_id: Optional[str] = None,
         buttons: Optional[list] = None, dedupe_key: Optional[str] = None) -> bool:
    """Send one Telegram message/photo; returns True when Telegram accepted it."""
    if not chat_id:
        _log(db, complaint_id=complaint_id, chat_id="", kind=kind, status="skipped",
             dedupe_key=dedupe_key, error="no chat id")
        db.commit()
        return False

    if dedupe_key and already_sent(db, dedupe_key):
        return False

    reply_markup = {"inline_keyboard": buttons} if buttons else None

    if not BOT_TOKEN:
        _log(db, complaint_id=complaint_id, chat_id=str(chat_id), kind=kind, status="skipped",
             dedupe_key=dedupe_key, error="TELEGRAM_BOT_TOKEN not configured")
        db.commit()
        logger.warning("TELEGRAM_BOT_TOKEN missing - notification '%s' skipped", kind)
        return False

    try:
        if photo_file_id:
            url = f"{API_BASE}/bot{BOT_TOKEN}/sendPhoto"
            payload = {"chat_id": chat_id, "photo": photo_file_id,
                       "caption": text, "parse_mode": "HTML"}
        else:
            url = f"{API_BASE}/bot{BOT_TOKEN}/sendMessage"
            payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                       "disable_web_page_preview": True}
        if reply_markup:
            payload["reply_markup"] = reply_markup

        resp = requests.post(url, json=payload, timeout=TIMEOUT)
        if resp.status_code != 200:
            _log(db, complaint_id=complaint_id, chat_id=str(chat_id), kind=kind,
                 status="failed", dedupe_key=dedupe_key,
                 error=f"HTTP {resp.status_code}: {resp.text[:300]}")
            db.commit()
            logger.error("Telegram send failed (%s): %s", resp.status_code, resp.text[:200])
            return False

        _log(db, complaint_id=complaint_id, chat_id=str(chat_id), kind=kind,
             status="sent", dedupe_key=dedupe_key)
        db.commit()
        return True
    except Exception as exc:  # network errors must never break the worker
        _log(db, complaint_id=complaint_id, chat_id=str(chat_id), kind=kind,
             status="failed", dedupe_key=dedupe_key, error=str(exc))
        db.commit()
        logger.error("Telegram send error: %s", exc)
        return False


# --------------------------------------------------------------------- layouts
def officer_buttons(complaint_id: str, *, allow_escalate: bool = False) -> list:
    """Inline keyboard; callback_data is short (Telegram limits it to 64 bytes)."""
    rows = [
        [
            {"text": "✅ Accept", "callback_data": f"c:ack:{complaint_id}"},
            {"text": "🔧 In Progress", "callback_data": f"c:prg:{complaint_id}"},
        ],
        [
            {"text": "📷 Submit Resolution", "callback_data": f"c:res:{complaint_id}"},
            {"text": "ℹ️ View Details", "callback_data": f"c:det:{complaint_id}"},
        ],
    ]
    if allow_escalate:
        rows.append([{"text": "⬆️ Escalate", "callback_data": f"c:esc:{complaint_id}"}])
    return rows


def deadline_text(complaint: Complaint) -> str:
    if not complaint.escalation_due_at:
        return "not set"
    return complaint.escalation_due_at.strftime("%d %b %Y, %H:%M UTC")


def assignment_message(complaint: Complaint, officer: Officer, department_name: str = "",
                       category_name: str = "") -> str:
    location = complaint.area or "Unknown area"
    if complaint.pincode:
        location += f" - {complaint.pincode}"
    return (
        "🚨 <b>New Grievance Assigned</b>\n"
        f"🎫 <b>Ticket:</b> {complaint.ticket_ref}\n"
        f"🏢 <b>Department:</b> {department_name or 'Unassigned'}\n"
        f"📂 <b>Category:</b> {category_name or 'General'}\n"
        f"⚠️ <b>Severity:</b> {complaint.severity}\n"
        f"📍 <b>Location:</b> {location}\n"
        f"🗺 <a href=\"{complaint.map_link}\">Open map</a>\n"
        f"📝 {complaint.description[:200]}\n"
        f"⏰ <b>Resolve by:</b> {deadline_text(complaint)}\n"
        f"👤 <b>Assigned to:</b> {officer.full_name} (L{officer.level})\n\n"
        "Use the buttons below, or reply to this message with an "
        "<b>after-resolution photo</b>."
    )


def escalation_message(complaint: Complaint, new_officer: Officer, reason: str,
                       department_name: str = "", category_name: str = "") -> str:
    location = complaint.area or "Unknown area"
    return (
        "⬆️ <b>Grievance Escalated To You</b>\n"
        f"🎫 <b>Ticket:</b> {complaint.ticket_ref}\n"
        f"🏢 <b>Department:</b> {department_name or '-'}\n"
        f"📂 <b>Category:</b> {category_name or '-'}\n"
        f"⚠️ <b>Severity:</b> {complaint.severity}\n"
        f"📍 <b>Location:</b> {location}\n"
        f"🗺 <a href=\"{complaint.map_link}\">Open map</a>\n"
        f"📝 {complaint.description[:200]}\n"
        f"📈 <b>Escalated to:</b> L{new_officer.level} ({new_officer.full_name})\n"
        f"🧾 <b>Reason:</b> {reason}\n"
        f"⏰ <b>Resolve by:</b> {deadline_text(complaint)}"
    )


def reminder_message(complaint: Complaint, officer: Officer) -> str:
    return (
        "⏳ <b>TAT Reminder</b>\n"
        f"🎫 <b>Ticket:</b> {complaint.ticket_ref}\n"
        f"📂 {complaint.description[:120]}\n"
        f"⏰ <b>Deadline:</b> {deadline_text(complaint)}\n"
        f"👤 <b>Owner:</b> {officer.full_name} (L{officer.level})"
    )


def citizen_status_message(complaint: Complaint, headline: str) -> str:
    return (
        f"{headline}\n"
        f"🎫 <b>Ticket:</b> {complaint.ticket_ref}\n"
        f"📌 <b>Status:</b> {complaint.status}\n"
        f"📍 <b>Location:</b> {complaint.area or 'Unknown'}"
    )

