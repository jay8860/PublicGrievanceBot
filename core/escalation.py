"""TAT + automatic L1->L4 escalation engine.

Design
------
* Deadlines are persisted (``complaints.escalation_due_at``), so the engine is
  restart-safe and does not depend on the dashboard being open.
* ``run_once()`` is a pure function of (database, clock): it can be driven by
  the API process scheduler, a standalone worker (``worker.py``) or a test.
* Every escalation writes ``escalation_history`` with a unique ``dedupe_key``;
  a second tick - or a second worker - cannot escalate the same complaint twice.
* A complaint is never auto-resolved: expiry only raises the responsible level.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import notify
from .audit import log_action
from .geo import OPEN_STATUSES, find_officer
from .models import (Category, Complaint, ComplaintHistory, Department,
                     EscalationHistory, EscalationRule, Officer)

logger = logging.getLogger(__name__)

MAX_LEVEL = 4


# ------------------------------------------------------------------- utilities
def get_rule(db: Session, department_id: Optional[str], category_id: Optional[str]) -> EscalationRule:
    """Category-specific rule wins, else department default, else in-memory default."""
    if category_id:
        rule = (db.query(EscalationRule)
                .filter(EscalationRule.category_id == category_id,
                        EscalationRule.active.is_(True))
                .order_by(EscalationRule.created_at.desc()).first())
        if rule:
            return rule
    if department_id:
        rule = (db.query(EscalationRule)
                .filter(EscalationRule.department_id == department_id,
                        EscalationRule.category_id.is_(None),
                        EscalationRule.active.is_(True))
                .first())
        if rule:
            return rule
    return EscalationRule(department_id=department_id or "", category_id=category_id)


def _is_working_day(day, rule: EscalationRule) -> bool:
    working = rule.working_days if rule.working_days is not None else [0, 1, 2, 3, 4, 5]
    holidays = rule.holidays or []
    return day.weekday() in working and day.strftime("%Y-%m-%d") not in holidays


def add_working_hours(start: datetime, hours: float, rule: EscalationRule) -> datetime:
    """Add ``hours`` then roll forward to the next working day if needed."""
    target = start + timedelta(hours=hours)
    guard = 0
    while not _is_working_day(target, rule) and guard < 14:
        target = target + timedelta(days=1)
        guard += 1
    return target


def deadline_for(rule: EscalationRule, level: int, start: Optional[datetime] = None) -> datetime:
    return add_working_hours(start or datetime.utcnow(), rule.hours_for_level(level), rule)


# --------------------------------------------------------------------- history
def add_history(db: Session, complaint: Complaint, action: str, *, actor_type="system",
                actor_id="", note="", to_level=None) -> None:
    db.add(ComplaintHistory(complaint_id=complaint.id, action=action, actor_type=actor_type,
                            actor_id=str(actor_id or ""), from_level=complaint.level,
                            to_level=to_level if to_level is not None else complaint.level,
                            note=note))


def dept_category_names(db: Session, complaint: Complaint):
    dept = db.get(Department, complaint.department_id) if complaint.department_id else None
    cat = db.get(Category, complaint.category_id) if complaint.category_id else None
    return (dept.name if dept else ""), (cat.name if cat else "")


def notify_officer(db: Session, complaint: Complaint, officer: Officer, text: str,
                   kind: str, dedupe_key: str, buttons: Optional[list] = None) -> bool:
    return notify.send(db, chat_id=officer.telegram_chat_id, text=text, kind=kind,
                       complaint_id=complaint.id,
                       buttons=buttons if buttons is not None else notify.officer_buttons(
                           complaint.id, allow_escalate=officer.level < MAX_LEVEL),
                       dedupe_key=dedupe_key)


def notify_citizen(db: Session, complaint: Complaint, headline: str, kind: str,
                   dedupe_key: str) -> None:
    notify.send(db, chat_id=complaint.citizen_chat_id,
                text=notify.citizen_status_message(complaint, headline),
                kind=kind, complaint_id=complaint.id, dedupe_key=dedupe_key)


# ------------------------------------------------------------------ assignment
def assign(db: Session, complaint: Complaint, officer: Optional[Officer], *,
           actor_type: str = "system", actor_id: str = "", reason: str = "") -> Complaint:
    """Assign/reassign a complaint, start its TAT and notify the officer."""
    rule = get_rule(db, complaint.department_id, complaint.category_id)
    dept_name, cat_name = dept_category_names(db, complaint)
    previous_officer_id = complaint.assigned_officer_id

    complaint.assigned_officer_id = officer.id if officer else None
    if officer:
        complaint.level = officer.level

    if officer is None:
        # Nobody configured for this sector/level - never assign randomly.
        complaint.status = "NEEDS_REVIEW"
        complaint.escalation_due_at = None
        add_history(db, complaint, "needs_review", actor_type=actor_type, actor_id=actor_id,
                    note=reason or "No matching officer for department/level/jurisdiction")
        log_action(db, "complaint.needs_review", actor_type=actor_type, actor_id=actor_id,
                   entity="complaint", entity_id=complaint.id, detail={"reason": reason})
        db.commit()
        return complaint

    if complaint.acknowledged_at is None:
        complaint.status = "ASSIGNED"
    complaint.escalation_due_at = deadline_for(rule, officer.level)
    complaint.reminder_sent_at = None
    add_history(db, complaint, "assigned", actor_type=actor_type, actor_id=actor_id,
                to_level=officer.level, note=reason or f"Assigned to {officer.full_name}")

    if complaint.escalation_count:
        text = notify.escalation_message(complaint, officer,
                                         reason or "manual reassignment",
                                         dept_name, cat_name)
        kind = "reassigned"
    else:
        text = notify.assignment_message(complaint, officer, dept_name, cat_name)
        kind = "assigned"

    notify_officer(db, complaint, officer, text, kind,
                   dedupe_key=f"assign:{complaint.id}:{officer.id}:{complaint.escalation_count}")
    notify_citizen(db, complaint, "✅ <b>Your complaint has been assigned to an officer.</b>",
                   "citizen_assigned", f"cit_assigned:{complaint.id}:{officer.id}")

    log_action(db, "complaint.assign", actor_type=actor_type, actor_id=actor_id,
               entity="complaint", entity_id=complaint.id,
               detail={"officer_id": officer.id, "level": officer.level,
                       "previous_officer_id": previous_officer_id})
    db.commit()
    return complaint


def route_new(db: Session, complaint: Complaint, **actor) -> Complaint:
    """Find the L1 officer for a brand-new complaint and assign it."""
    officer = find_officer(db, department_id=complaint.department_id, level=1,
                           ward=complaint.ward, village=complaint.village,
                           block=complaint.block, area=complaint.area)
    return assign(db, complaint, officer, reason="initial routing", **actor)


# --------------------------------------------------------------------- the tick
def _escalation_target(db: Session, complaint: Complaint) -> Optional[Officer]:
    """Next responsible officer: level+1 in the same department/jurisdiction."""
    next_level = complaint.level + 1
    officer = find_officer(db, department_id=complaint.department_id, level=next_level,
                           ward=complaint.ward, village=complaint.village,
                           block=complaint.block, area=complaint.area)
    if officer:
        return officer
    # Fall back to any active officer of that level in the department (district
    # authorities usually carry no ward-level jurisdiction).
    return (db.query(Officer)
            .filter(Officer.department_id == complaint.department_id,
                    Officer.level == next_level,
                    Officer.active.is_(True))
            .order_by(Officer.created_at.asc())
            .first())


def _escalate(db: Session, complaint: Complaint, rule: EscalationRule, now: datetime) -> bool:
    from_level = complaint.level
    to_level = min(from_level + 1, MAX_LEVEL)
    reason = f"TAT expired at L{from_level} without resolution"
    dedupe = f"esc:{complaint.id}:{from_level}->{to_level}"

    if db.query(EscalationHistory.id).filter(EscalationHistory.dedupe_key == dedupe).first():
        return False

    target = _escalation_target(db, complaint)

    db.add(EscalationHistory(complaint_id=complaint.id, from_level=from_level,
                             to_level=to_level,
                             from_officer_id=complaint.assigned_officer_id,
                             to_officer_id=target.id if target else None,
                             reason=reason, automatic=True, dedupe_key=dedupe))
    try:
        db.flush()          # unique dedupe_key -> the race loser aborts here
    except IntegrityError:
        db.rollback()
        return False

    complaint.level = to_level
    complaint.escalation_count = (complaint.escalation_count or 0) + 1
    complaint.status = "ESCALATED"
    complaint.assigned_officer_id = target.id if target else None
    complaint.reminder_sent_at = None
    complaint.escalation_due_at = deadline_for(rule, to_level, now) if target else None

    add_history(db, complaint, "escalated", note=reason, to_level=to_level)

    dept_name, cat_name = dept_category_names(db, complaint)
    if target:
        notify_officer(db, complaint, target,
                       notify.escalation_message(complaint, target, reason, dept_name, cat_name),
                       "escalated", f"esc_msg:{complaint.id}:{to_level}")
        notify_citizen(db, complaint,
                       f"⬆️ <b>Your complaint was escalated to level {to_level}.</b>",
                       "citizen_escalated", f"cit_esc:{complaint.id}:{to_level}")
    else:
        # No officer at the next level: alert the fallback admin and park the
        # complaint for review instead of silently losing it.
        from config import get_env
        complaint.status = "NEEDS_REVIEW"
        notify.send(db, chat_id=get_env("DEFAULT_OFFICER_CHAT_ID"),
                    kind="escalation_unrouted", complaint_id=complaint.id,
                    text=(f"⚠️ <b>No L{to_level} officer configured</b> for ticket "
                          f"{complaint.ticket_ref}. Complaint parked for administrative review."),
                    dedupe_key=f"esc_unrouted:{complaint.id}:{to_level}")

    log_action(db, "complaint.escalate", entity="complaint", entity_id=complaint.id,
               detail={"from_level": from_level, "to_level": to_level,
                       "automatic": True, "reason": reason})
    db.commit()
    return True


def _remind(db: Session, complaint: Complaint, rule: EscalationRule, now: datetime) -> bool:
    if not complaint.escalation_due_at or not complaint.assigned_officer_id:
        return False
    if complaint.reminder_sent_at is not None:
        return False
    if now < complaint.escalation_due_at - timedelta(hours=rule.reminder_hours or 0):
        return False

    officer = db.get(Officer, complaint.assigned_officer_id)
    if not officer:
        return False

    notify_officer(db, complaint, officer, notify.reminder_message(complaint, officer),
                   "reminder", f"rem:{complaint.id}:{complaint.level}")
    complaint.reminder_sent_at = now
    add_history(db, complaint, "reminder_sent", note="TAT reminder sent")
    db.commit()
    return True


def run_once(db: Session, now: Optional[datetime] = None) -> dict:
    """One engine tick: reminders first, then escalations. Returns a summary."""
    now = now or datetime.utcnow()
    summary = {"reminders": 0, "escalations": 0, "checked": 0, "errors": 0}

    due = (db.query(Complaint)
           .filter(Complaint.status.in_(OPEN_STATUSES),
                   Complaint.escalation_due_at.isnot(None),
                   Complaint.escalation_due_at <= now + timedelta(hours=24))
           .all())

    for complaint in due:
        summary["checked"] += 1
        if complaint.sla_paused_at is not None:
            continue
        rule = get_rule(db, complaint.department_id, complaint.category_id)
        try:
            if complaint.escalation_due_at and complaint.escalation_due_at <= now:
                if complaint.level >= MAX_LEVEL:
                    # Final level: alert once, never auto-close.
                    officer = (db.get(Officer, complaint.assigned_officer_id)
                               if complaint.assigned_officer_id else None)
                    if officer:
                        notify_officer(db, complaint, officer,
                                       f"🚨 <b>L4 review overdue</b> for {complaint.ticket_ref}",
                                       "l4_overdue", f"l4_overdue:{complaint.id}")
                    complaint.escalation_due_at = None
                    db.commit()
                elif _escalate(db, complaint, rule, now):
                    summary["escalations"] += 1
            elif _remind(db, complaint, rule, now):
                summary["reminders"] += 1
        except Exception as exc:          # one bad row must not stop the tick
            db.rollback()
            summary["errors"] += 1
            logger.exception("Escalation tick failed for %s: %s", complaint.ticket_ref, exc)

    return summary


def pause_sla(db: Session, complaint: Complaint, reason: str, actor: str) -> None:
    """Documented SLA pause (e.g. awaiting citizen information)."""
    if complaint.sla_paused_at is None:
        complaint.sla_paused_at = datetime.utcnow()
        complaint.sla_pause_reason = reason[:300]
        complaint.sla_paused_by = actor
        add_history(db, complaint, "sla_paused", actor_type="admin", actor_id=actor, note=reason)
        log_action(db, "complaint.sla_pause", actor_type="admin", actor_id=actor,
                   entity="complaint", entity_id=complaint.id, detail={"reason": reason})
        db.commit()


def resume_sla(db: Session, complaint: Complaint, actor: str) -> None:
    """Shift the deadline by however long the pause lasted."""
    if complaint.sla_paused_at is None:
        return
    paused_for = datetime.utcnow() - complaint.sla_paused_at
    if complaint.escalation_due_at:
        complaint.escalation_due_at = complaint.escalation_due_at + paused_for
    complaint.sla_paused_at = None
    complaint.sla_pause_reason = ""
    complaint.sla_paused_by = ""
    add_history(db, complaint, "sla_resumed", actor_type="admin", actor_id=actor,
                note=f"paused for {paused_for}")
    log_action(db, "complaint.sla_resume", actor_type="admin", actor_id=actor,
               entity="complaint", entity_id=complaint.id)
    db.commit()



