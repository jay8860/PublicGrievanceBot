"""Telegram <-> platform bridge.

Kept separate from ``bot.py`` so the citizen conversation handler stays intact:
this module owns officer onboarding, inline-button actions and mirroring bot
complaints/resolutions into the new database.
"""
import logging
import re

from config import get_env

from .db import SessionLocal
from .models import Complaint, Officer
from . import service

logger = logging.getLogger(__name__)

CODE_PATTERN = re.compile(r"^GRV-[0-9A-F]{8}$", re.IGNORECASE)
TICKET_PATTERN = re.compile(r"(GRV-\d{4}-\d{6})", re.IGNORECASE)
PLATFORM_ENABLED = get_env("PLATFORM_DB_ENABLED", "true").lower() not in ("0", "false", "no", "off")


def officer_for_chat(db, chat_id):
    return (db.query(Officer)
            .filter(Officer.telegram_chat_id == str(chat_id), Officer.active.is_(True))
            .one_or_none())


def record_complaint(*, citizen_chat_id, analysis: dict, lat, lon, accuracy,
                     geo_info: dict, photo_file_id: str, block: str = "",
                     ward: str = "", village: str = "") -> dict:
    """Mirror a citizen report into the platform DB and route it.

    Returns {'ticket': ref|None, 'assigned': bool, 'note': str}. Never raises:
    the Telegram + Sheets flow must keep working even if the DB is unavailable.
    """
    if not PLATFORM_ENABLED:
        return {"ticket": None, "assigned": False, "note": ""}

    db = SessionLocal()
    try:
        complaint = service.create_complaint(
            db,
            citizen_chat_id=citizen_chat_id,
            description=analysis.get("description", ""),
            category_label=analysis.get("category"),
            severity=analysis.get("severity", "Medium"),
            lat=lat, lon=lon, accuracy_m=accuracy,
            pincode=(geo_info or {}).get("pincode", ""),
            area=(geo_info or {}).get("area", ""),
            ward=ward, village=village, block=block,
            photo_file_id=photo_file_id,
            ai_raw=analysis, ai_confidence=float(analysis.get("confidence") or 0) or 0.0,
        )
        assigned = complaint.assigned_officer_id is not None
        return {"ticket": complaint.ticket_ref, "assigned": assigned,
                "note": "" if assigned else "Queued for administrative review."}
    except Exception as exc:
        logger.error("Platform DB mirror failed: %s", exc)
        return {"ticket": None, "assigned": False, "note": ""}
    finally:
        db.close()


def link_officer(chat_id, code: str) -> tuple[str, bool]:
    """Redeem an invitation code. Returns (message, success)."""
    db = SessionLocal()
    try:
        officer, error = service.redeem_invitation(db, code, chat_id)
        if error:
            return error, False
        dept = officer.department_id
        return (f"✅ Linked to <b>{officer.full_name}</b> (Level {officer.level}).\n"
                "You will now receive grievance assignments here."), True
    except Exception as exc:
        logger.error("Officer linking failed: %s", exc)
        return "Could not complete linking right now. Please try again.", False
    finally:
        db.close()


def resolve_from_officer(chat_id, ticket_ref: str, after_file_id: str) -> str:
    """Officer replied with an after photo -> resolve the platform complaint."""
    db = SessionLocal()
    try:
        officer = officer_for_chat(db, chat_id)
        complaint = (db.query(Complaint)
                     .filter(Complaint.ticket_ref == ticket_ref.upper()).one_or_none())
        if not complaint:
            return ""
        if not officer or not service.officer_may_act(db, complaint, officer):
            return "⛔ This complaint is outside your department/level."

        result = service.resolve(db, complaint, officer=officer, after_file_id=after_file_id,
                                 notes="resolved from Telegram", actor_type="officer",
                                 actor_id=officer.id, run_verification=True)
        if result.get("auto_approved"):
            return "✅ Photo check passed. Resolution auto-approved; the citizen has been asked to confirm."
        verdict = (result.get("verification") or {}).get("verdict")
        if verdict:
            return (f"🧪 Photo check result: <b>{verdict.replace('_', ' ').title()}</b>. "
                    "Sent to Resolution Verification for a decision.")
        return "📋 Sent to Resolution Verification (photo check unavailable)."

    except Exception as exc:
        logger.error("Platform resolution failed: %s", exc)
        return ""
    finally:
        db.close()


# ------------------------------------------------------------ Telegram handlers
async def _safe_edit(query, text: str) -> None:
    """Photo captions cannot be edited as text - fall back to a new message."""
    try:
        await query.edit_message_text(text, parse_mode="HTML")
    except Exception:
        try:
            await query.message.reply_text(text, parse_mode="HTML")
        except Exception:
            logger.warning("Could not update the callback message")


def _details_text(db, complaint: Complaint) -> str:
    from .models import Category, Department

    dept = db.get(Department, complaint.department_id) if complaint.department_id else None
    cat = db.get(Category, complaint.category_id) if complaint.category_id else None
    deadline = (complaint.escalation_due_at.strftime("%d %b %Y, %H:%M UTC")
                if complaint.escalation_due_at else "not set")
    return (
        f"🎫 <b>{complaint.ticket_ref}</b>\n"
        f"🏢 {dept.name if dept else '-'}\n"
        f"📂 {cat.name if cat else '-'}\n"
        f"⚠️ Severity: {complaint.severity}\n"
        f"📌 Status: {complaint.status} (L{complaint.level})\n"
        f"📍 {complaint.area or 'Unknown'} {complaint.pincode or ''}\n"
        f"🗺 <a href=\"{complaint.map_link}\">Open map</a>\n"
        f"📝 {complaint.description[:250]}\n"
        f"⏰ Resolve by: {deadline}\n"
        f"📈 Escalations: {complaint.escalation_count} | Reopened: {complaint.reopened_count}"
    )


async def officer_callback(update, context) -> None:
    """Validate + apply an inline-button action coming from an officer."""
    query = update.callback_query
    parts = (query.data or "").split(":")
    if len(parts) != 3 or parts[0] != "c":
        await query.answer()
        return

    action, complaint_id = parts[1], parts[2]
    db = SessionLocal()
    try:
        officer = officer_for_chat(db, query.from_user.id)
        if not officer:
            await query.answer("This Telegram account is not linked to an officer.", show_alert=True)
            return

        complaint = db.get(Complaint, complaint_id)
        if not complaint:
            await query.answer("Complaint not found.", show_alert=True)
            return
        if not service.officer_may_act(db, complaint, officer):
            await query.answer("This complaint is outside your department/level.", show_alert=True)
            return

        if action == "ack":
            service.acknowledge(db, complaint, officer)
            await query.answer("Acknowledged")
            await _safe_edit(query, f"✅ <b>Acknowledged</b>\n{_details_text(db, complaint)}")

        elif action == "prg":
            service.mark_in_progress(db, complaint, officer, note="started work from Telegram")
            await query.answer("Marked in progress")
            await _safe_edit(query, f"🔧 <b>In progress</b>\n{_details_text(db, complaint)}")

        elif action == "det":
            await query.answer()
            await _safe_edit(query, _details_text(db, complaint))

        elif action == "res":
            await query.answer()
            await query.message.reply_text(
                "📷 Reply to <b>this message</b> with the after-resolution photo.\n"
                f"Ticket: <code>{complaint.ticket_ref}</code>", parse_mode="HTML")

        elif action == "esc":
            from datetime import datetime

            from . import escalation
            if complaint.level >= escalation.MAX_LEVEL:
                await query.answer("Already at the highest level.", show_alert=True)
                return
            rule = escalation.get_rule(db, complaint.department_id, complaint.category_id)
            escalation._escalate(db, complaint, rule, datetime.utcnow())
            await query.answer("Escalated")
            await _safe_edit(query, f"⬆️ <b>Escalated to L{complaint.level}</b>\n"
                                    f"{_details_text(db, complaint)}")
        else:
            await query.answer()
    except Exception as exc:
        logger.exception("Officer callback failed: %s", exc)
        try:
            await query.answer("Action failed - see server logs.", show_alert=True)
        except Exception:
            pass
    finally:
        db.close()


async def officer_code_message(update, context) -> None:
    """Any plain message that looks like an invitation code links the officer."""
    text = (update.message.text or "").strip()
    if not CODE_PATTERN.match(text):
        return
    message, _ok = link_officer(update.effective_chat.id, text)
    await update.message.reply_text(message, parse_mode="HTML")


async def officer_command(update, context) -> None:
    """/officer <code> - onboarding, or show the current link status."""
    args = getattr(context, "args", None) or []
    if args:
        message, _ok = link_officer(update.effective_chat.id, args[0])
        await update.message.reply_text(message, parse_mode="HTML")
        return

    db = SessionLocal()
    try:
        officer = officer_for_chat(db, update.effective_chat.id)
        if officer:
            await update.message.reply_text(
                f"👤 Linked as <b>{officer.full_name}</b> (Level {officer.level}).",
                parse_mode="HTML")
        else:
            await update.message.reply_text(
                "Send your invitation code like this: <code>/officer GRV-1A2B3C4D</code>",
                parse_mode="HTML")
    finally:
        db.close()


def register_platform_handlers(application) -> None:
    """Attach the platform handlers without touching the citizen conversation."""
    from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, filters

    application.add_handler(CommandHandler("officer", officer_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,
                                          officer_code_message), group=1)
    application.add_handler(CallbackQueryHandler(officer_callback, pattern=r"^c:"))


