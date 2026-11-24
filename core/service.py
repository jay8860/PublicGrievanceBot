"""Complaint lifecycle + officer invitations (single place both the bot and the
HTTP API call into, so Telegram and the dashboard can never disagree)."""
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import get_env

from . import escalation, notify, verify
from .audit import log_action
from .geo import find_duplicate_group
from .models import (Category, CitizenFeedback, Complaint, ComplaintHistory,
                     ComplaintImage, Department, EscalationRule, InvitationCode,
                     Officer, TelegramMapping)

logger = logging.getLogger(__name__)

TICKET_PREFIX = get_env("TICKET_PREFIX", "GRV")
OPEN_FOR_FEEDBACK = ("RESOLVED", "VERIFIED")


def next_ticket_ref(db: Session) -> str:
    year = datetime.utcnow().year
    prefix = f"{TICKET_PREFIX}-{year}-"
    used = db.query(func.count(Complaint.id)).filter(Complaint.ticket_ref.like(prefix + "%")).scalar() or 0
    return f"{prefix}{used + 1:06d}"


def resolve_category(db: Session, label: Optional[str]) -> Optional[Category]:
    """Map the AI's label onto a configured category (case-insensitive)."""
    if not label:
        return None
    wanted = label.strip().lower()
    rows = (db.query(Category)
            .join(Department, Category.department_id == Department.id)
            .filter(Category.active.is_(True), func.lower(Category.ai_label) == wanted)
            .order_by(Department.code.asc())
            .all())
    if rows:
        return rows[0]
    # Fall back to a name match so admin-renamed categories still resolve.
    return (db.query(Category)
            .filter(Category.active.is_(True), func.lower(Category.name) == wanted)
            .first())


def create_complaint(db: Session, *, citizen_chat_id, description: str = "",
                     category_label: Optional[str] = None, severity: str = "Medium",
                     lat: Optional[float] = None, lon: Optional[float] = None,
                     accuracy_m: Optional[float] = None, pincode: str = "",
                     area: str = "", ward: str = "", village: str = "", block: str = "",
                     photo_file_id: str = "", photo_bytes: Optional[bytes] = None,
                     ai_raw: Optional[dict] = None, ai_confidence: float = 0.0) -> Complaint:
    """Create + route one complaint (never discards; duplicates are grouped)."""
    category = resolve_category(db, category_label)
    department_id = category.department_id if category else None

    complaint = Complaint(
        ticket_ref=next_ticket_ref(db),
        citizen_chat_id=str(citizen_chat_id),
        department_id=department_id,
        category_id=category.id if category else None,
        severity=(severity or "Medium").title(),
        description=description or "",
        lat=lat, lon=lon, accuracy_m=accuracy_m,
        pincode=pincode or "", area=area or "", ward=ward or "",
        village=village or "", block=block or "",
        map_link=(f"https://www.google.com/maps?q={lat},{lon}" if lat is not None and lon is not None else ""),
        ai_raw=ai_raw or {}, ai_confidence=ai_confidence or 0.0,
        status="NEW",
    )

    group_id = find_duplicate_group(db, category_id=complaint.category_id, lat=lat, lon=lon)
    if group_id:
        complaint.group_id = group_id

    db.add(complaint)
    try:
        db.flush()
    except IntegrityError:      # ticket_ref collision under concurrency -> retry once
        db.rollback()
        complaint.ticket_ref = next_ticket_ref(db) + "-R"
        db.add(complaint)
        db.flush()

    db.add(ComplaintImage(complaint_id=complaint.id, kind="original",
                          telegram_file_id=photo_file_id or "",
                          storage_key="", url=""))
    escalation.add_history(db, complaint, "created", actor_type="citizen",
                           actor_id=str(citizen_chat_id), note="Complaint submitted")
    log_action(db, "complaint.create", actor_type="citizen", actor_id=str(citizen_chat_id),
               entity="complaint", entity_id=complaint.id,
               detail={"ticket": complaint.ticket_ref, "category": category_label,
                       "grouped": bool(group_id)})
    db.commit()

    if complaint.category_id is None:
        complaint.status = "NEEDS_REVIEW"
        escalation.add_history(db, complaint, "needs_review",
                               note=f"Unrecognised category '{category_label}'")
        db.commit()
        return complaint

    return escalation.route_new(db, complaint)


def officer_may_act(db: Session, complaint: Complaint, officer: Officer) -> bool:
    """Department + level scope check used by the bot and the API."""
    if not officer or not officer.active:
        return False
    if complaint.department_id and officer.department_id != complaint.department_id:
        return False
    if complaint.assigned_officer_id == officer.id:
        return True
    return officer.level >= complaint.level


# ------------------------------------------------------------------- actions
def acknowledge(db: Session, complaint: Complaint, officer: Officer) -> Complaint:
    if complaint.acknowledged_at is None:
        complaint.acknowledged_at = datetime.utcnow()
    if complaint.status in ("ASSIGNED", "NEW", "ESCALATED", "REOPENED"):
        complaint.status = "ACKNOWLEDGED"
    escalation.add_history(db, complaint, "acknowledged", actor_type="officer",
                           actor_id=officer.id, note=f"{officer.full_name} accepted")
    log_action(db, "complaint.acknowledge", actor_type="officer", actor_id=officer.id,
               entity="complaint", entity_id=complaint.id)
    db.commit()
    return complaint


def mark_in_progress(db: Session, complaint: Complaint, officer: Officer, note: str = "") -> Complaint:
    if complaint.acknowledged_at is None:
        complaint.acknowledged_at = datetime.utcnow()
    if complaint.first_action_at is None:
        complaint.first_action_at = datetime.utcnow()
    complaint.status = "IN_PROGRESS"
    escalation.add_history(db, complaint, "in_progress", actor_type="officer",
                           actor_id=officer.id, note=note)
    log_action(db, "complaint.in_progress", actor_type="officer", actor_id=officer.id,
               entity="complaint", entity_id=complaint.id)
    db.commit()
    return complaint


def _telegram_photo_bytes(file_id: str) -> Optional[bytes]:
    """Best-effort download of a Telegram photo (for before/after comparison)."""
    from . import notify as tg

    if not file_id or not tg.BOT_TOKEN:
        return None
    try:
        import requests
        info = requests.get(f"{tg.API_BASE}/bot{tg.BOT_TOKEN}/getFile",
                            params={"file_id": file_id}, timeout=15).json()
        path = (info.get("result") or {}).get("file_path")
        if not path:
            return None
        resp = requests.get(f"{tg.API_BASE}/file/bot{tg.BOT_TOKEN}/{path}", timeout=30)
        return resp.content if resp.status_code == 200 else None
    except Exception as exc:
        logger.warning("Could not download original photo: %s", exc)
        return None


def resolve(db: Session, complaint: Complaint, *, officer: Optional[Officer] = None,
            after_bytes: Optional[bytes] = None, after_file_id: str = "",
            notes: str = "", actor_type: str = "officer", actor_id: str = "",
            run_verification: bool = True) -> dict:
    """Officer submits an after-resolution photo -> AI verdict + citizen notice."""
    import hashlib

    complaint.status = "RESOLVED"
    complaint.resolved_at = datetime.utcnow()
    complaint.escalation_due_at = None
    complaint.resolution_notes = notes or complaint.resolution_notes

    if after_bytes or after_file_id:
        db.add(ComplaintImage(complaint_id=complaint.id, kind="resolution",
                              telegram_file_id=after_file_id or "",
                              sha256=hashlib.sha256(after_bytes).hexdigest() if after_bytes else ""))

    actor = actor_id or (officer.id if officer else "")
    escalation.add_history(db, complaint, "resolved", actor_type=actor_type,
                           actor_id=actor, note=notes)
    log_action(db, "complaint.resolve", actor_type=actor_type, actor_id=actor,
               entity="complaint", entity_id=complaint.id,
               detail={"verification": "pending" if run_verification else "skipped"})
    db.commit()

    verdict = None
    if run_verification:
        original_row = (db.query(ComplaintImage)
                        .filter(ComplaintImage.complaint_id == complaint.id,
                                ComplaintImage.kind == "original").first())
        original = (_telegram_photo_bytes(original_row.telegram_file_id)
                    if original_row and original_row.telegram_file_id else None)
        after = after_bytes or (_telegram_photo_bytes(after_file_id) if after_file_id else None)
        if original and after:
            category = db.get(Category, complaint.category_id) if complaint.category_id else None
            verdict = verify.verify_resolution(original, after, complaint.description,
                                              category.name if category else "")
            complaint.resolution_verification = verdict["verdict"]
            log_action(db, "complaint.verification", entity="complaint",
                       entity_id=complaint.id, detail=verdict)
        else:
            complaint.resolution_verification = "requires_review"
        db.commit()

    notify.send(db, chat_id=complaint.citizen_chat_id, kind="citizen_resolved",
                complaint_id=complaint.id,
                text=(f"✅ <b>Your complaint {complaint.ticket_ref} was marked resolved.</b>\n"
                      "If the issue is fixed, please confirm. If not, you can reopen it."),
                photo_file_id=after_file_id or None,
                dedupe_key=f"cit_resolved:{complaint.id}:{complaint.resolved_at.timestamp()}")

    return {"complaint": complaint, "verification": verdict}


def citizen_feedback(db: Session, complaint: Complaint, *, confirmed: Optional[bool],
                     rating: Optional[int] = None, comment: str = "") -> Complaint:
    """Citizen confirms the fix (close) or reports it is still broken (reopen)."""
    db.add(CitizenFeedback(complaint_id=complaint.id, rating=rating, comment=comment,
                           resolution_confirmed=confirmed))
    if confirmed is True:
        complaint.status = "CLOSED"
        complaint.closed_at = datetime.utcnow()
        escalation.add_history(db, complaint, "citizen_confirmed", actor_type="citizen",
                               actor_id=complaint.citizen_chat_id)
    log_action(db, "complaint.feedback", actor_type="citizen", actor_id=complaint.citizen_chat_id,
               entity="complaint", entity_id=complaint.id,
               detail={"rating": rating, "confirmed": confirmed})
    db.commit()

    if confirmed is False:
        return reopen(db, complaint, reason=comment or "Citizen reports the issue still exists",
                      actor_type="citizen", actor_id=complaint.citizen_chat_id)
    return complaint


def reopen(db: Session, complaint: Complaint, *, reason: str, actor_type: str = "citizen",
           actor_id: str = "") -> Complaint:
    """Reopen without losing history; the TAT restarts at L1."""
    complaint.reopened_count = (complaint.reopened_count or 0) + 1
    complaint.resolved_at = None
    complaint.closed_at = None
    complaint.status = "REOPENED"
    complaint.resolution_verification = ""
    escalation.add_history(db, complaint, "reopened", actor_type=actor_type,
                           actor_id=actor_id, note=reason)
    log_action(db, "complaint.reopen", actor_type=actor_type, actor_id=actor_id,
               entity="complaint", entity_id=complaint.id, detail={"reason": reason})
    db.commit()

    officer = (db.query(Officer)
               .filter(Officer.department_id == complaint.department_id, Officer.level == 1,
                       Officer.active.is_(True))
               .order_by(Officer.created_at.asc()).first())
    return escalation.assign(db, complaint, officer, actor_type=actor_type, actor_id=actor_id,
                             reason=f"reopened: {reason}")


# --------------------------------------------------------------- invitations
def create_invitation(db: Session, officer: Officer, created_by: str,
                      ttl_hours: int = 48) -> InvitationCode:
    """Single-use, expiring code the officer types into the officer bot."""
    code = ""
    for _ in range(5):
        candidate = "GRV-" + secrets.token_hex(4).upper()
        if not db.query(InvitationCode.id).filter(InvitationCode.code == candidate).first():
            code = candidate
            break

    invitation = InvitationCode(code=code, officer_id=officer.id,
                                expires_at=datetime.utcnow() + timedelta(hours=ttl_hours),
                                created_by=created_by)
    db.add(invitation)
    log_action(db, "officer.invitation_created", actor_type="admin", actor_id=created_by,
               entity="officer", entity_id=officer.id,
               detail={"code": code, "ttl_hours": ttl_hours})
    db.commit()
    return invitation


def redeem_invitation(db: Session, code: str, chat_id) -> tuple[Optional[Officer], str]:
    """Link a Telegram chat to an officer profile. Returns (officer, error)."""
    chat_id = str(chat_id)
    invitation = (db.query(InvitationCode)
                  .filter(InvitationCode.code == (code or "").strip().upper())
                  .one_or_none())
    if not invitation:
        return None, "This invitation code does not exist."
    if invitation.revoked_at:
        return None, "This invitation code was revoked."
    if invitation.used_at:
        return None, "This invitation code has already been used."
    if invitation.expires_at < datetime.utcnow():
        return None, "This invitation code has expired. Ask your administrator for a new one."
    if db.query(Officer.id).filter(Officer.telegram_chat_id == chat_id).first():
        return None, "This Telegram account is already linked to an officer."

    officer = db.get(Officer, invitation.officer_id)
    if not officer or not officer.active:
        return None, "The officer account for this code is inactive."

    officer.telegram_chat_id = chat_id
    officer.telegram_linked_at = datetime.utcnow()
    officer.telegram_revoked_at = None
    invitation.used_at = datetime.utcnow()
    invitation.used_by_chat_id = chat_id
    db.add(TelegramMapping(chat_id=chat_id, officer_id=officer.id))

    # Single-use semantics: any other outstanding code for this officer dies.
    for other in (db.query(InvitationCode)
                  .filter(InvitationCode.officer_id == officer.id,
                          InvitationCode.id != invitation.id,
                          InvitationCode.used_at.is_(None)).all()):
        other.revoked_at = other.revoked_at or datetime.utcnow()

    log_action(db, "officer.telegram_linked", actor_type="officer", actor_id=officer.id,
               entity="officer", entity_id=officer.id, detail={"chat_id": chat_id})
    db.commit()
    return officer, ""


def revoke_telegram_access(db: Session, officer: Officer, reason: str, actor: str) -> None:
    officer.telegram_chat_id = None
    officer.telegram_revoked_at = datetime.utcnow()
    for mapping in (db.query(TelegramMapping)
                    .filter(TelegramMapping.officer_id == officer.id,
                            TelegramMapping.unlinked_at.is_(None)).all()):
        mapping.unlinked_at = datetime.utcnow()
        mapping.unlinked_reason = reason[:200]
    log_action(db, "officer.telegram_revoked", actor_type="admin", actor_id=actor,
               entity="officer", entity_id=officer.id, detail={"reason": reason})
    db.commit()


