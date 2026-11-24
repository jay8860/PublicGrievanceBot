"""Admin/operations API (prefix ``/api/v2``): departments, officers, TAT rules,
complaints, escalation centre, analytics, reports and audit logs.

Design rules
------------
* Additive only: the legacy ``/api/*`` endpoints keep serving the existing
  dashboard untouched.
* Every mutation is role-checked (``require_admin``/``require_superadmin``) and
  written to ``audit_logs``.
* Responses are plain dicts so the React app consumes them without codegen.
"""
import csv
import io
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from core import escalation, service
from core.audit import log_action
from core.db import get_session
from core.geo import OPEN_STATUSES
from core.models import (Category, CitizenFeedback, Complaint, ComplaintHistory,
                         ComplaintImage, Department, EscalationHistory,
                         EscalationRule, InvitationCode, Officer,
                         OfficerJurisdiction)
from core.security import (Principal, get_principal, hash_password,
                          require_admin, require_superadmin)

router = APIRouter(prefix="/api/v2", tags=["v2"])


# ------------------------------------------------------------------- payloads
class DepartmentIn(BaseModel):
    code: str = Field(min_length=2, max_length=32)
    name: str = Field(min_length=2, max_length=120)
    description: str = ""
    active: bool = True


class CategoryIn(BaseModel):
    department_id: str
    name: str = Field(min_length=2, max_length=120)
    ai_label: str = ""
    description: str = ""
    active: bool = True


class RuleIn(BaseModel):
    ack_hours: int = 12
    action_hours: int = 24
    l1_hours: int = 48
    l2_hours: int = 24
    l3_hours: int = 24
    l4_hours: int = 48
    reminder_hours: int = 6
    working_days: List[int] = [0, 1, 2, 3, 4, 5]
    holidays: List[str] = []


class JurisdictionIn(BaseModel):
    scope_type: str = Field(pattern="^(district|block|ward|village)$")
    scope_value: str


class OfficerIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    designation: str = ""
    department_id: Optional[str] = None
    level: int = Field(default=1, ge=1, le=4)
    employee_code: str = ""
    mobile: str = ""
    email: str = ""
    jurisdiction_type: str = "district"
    jurisdiction_value: str = ""
    reports_to_id: Optional[str] = None
    available: bool = True
    active: bool = True
    jurisdictions: List[JurisdictionIn] = []


class OfficerPatch(BaseModel):
    full_name: Optional[str] = None
    designation: Optional[str] = None
    department_id: Optional[str] = None
    level: Optional[int] = Field(default=None, ge=1, le=4)
    employee_code: Optional[str] = None
    mobile: Optional[str] = None
    email: Optional[str] = None
    jurisdiction_type: Optional[str] = None
    jurisdiction_value: Optional[str] = None
    reports_to_id: Optional[str] = None
    available: Optional[bool] = None
    active: Optional[bool] = None


class AssignIn(BaseModel):
    officer_id: Optional[str] = None
    reason: str = ""


class NoteIn(BaseModel):
    note: str = ""


class PauseIn(BaseModel):
    reason: str = Field(min_length=3, max_length=300)


class ResolveIn(BaseModel):
    notes: str = ""
    run_verification: bool = False


class FeedbackIn(BaseModel):
    confirmed: bool
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    comment: str = ""


class InvitationIn(BaseModel):
    ttl_hours: int = Field(default=48, ge=1, le=720)


class AdminIn(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=8, max_length=128)
    role: str = "admin"


# -------------------------------------------------------------------- helpers
def _dept(db: Session, department_id: str) -> Department:
    dept = db.get(Department, department_id)
    if not dept:
        raise HTTPException(404, "Department not found")
    return dept


def _officer(db: Session, officer_id: str) -> Officer:
    officer = db.get(Officer, officer_id)
    if not officer:
        raise HTTPException(404, "Officer not found")
    return officer


def _complaint(db: Session, complaint_id: str) -> Complaint:
    complaint = db.get(Complaint, complaint_id)
    if not complaint:
        raise HTTPException(404, "Complaint not found")
    return complaint


def _iso(value: Optional[datetime]):
    return value.isoformat() + "Z" if value else None


def department_out(db: Session, dept: Department) -> dict:
    return {
        "id": dept.id, "code": dept.code, "name": dept.name,
        "description": dept.description, "active": dept.active,
        "categories": (db.query(func.count(Category.id))
                       .filter(Category.department_id == dept.id).scalar() or 0),
        "officers": (db.query(func.count(Officer.id))
                     .filter(Officer.department_id == dept.id,
                             Officer.active.is_(True)).scalar() or 0),
        "open_complaints": (db.query(func.count(Complaint.id))
                            .filter(Complaint.department_id == dept.id,
                                    Complaint.status.in_(OPEN_STATUSES)).scalar() or 0),
    }


def officer_out(db: Session, officer: Officer) -> dict:
    scopes = (db.query(OfficerJurisdiction)
              .filter(OfficerJurisdiction.officer_id == officer.id).all())
    open_load = (db.query(func.count(Complaint.id))
                 .filter(Complaint.assigned_officer_id == officer.id,
                         Complaint.status.in_(OPEN_STATUSES)).scalar() or 0)
    resolved = (db.query(func.count(Complaint.id))
                .filter(Complaint.assigned_officer_id == officer.id,
                        Complaint.status.in_(("RESOLVED", "VERIFIED", "CLOSED"))).scalar() or 0)
    dept = db.get(Department, officer.department_id) if officer.department_id else None
    return {
        "id": officer.id, "full_name": officer.full_name,
        "designation": officer.designation, "employee_code": officer.employee_code,
        "department_id": officer.department_id,
        "department": dept.name if dept else None,
        "level": officer.level, "mobile": officer.mobile, "email": officer.email,
        "telegram_chat_id": officer.telegram_chat_id,
        "telegram_connected": bool(officer.telegram_chat_id),
        "telegram_linked_at": _iso(officer.telegram_linked_at),
        "jurisdiction_type": officer.jurisdiction_type,
        "jurisdiction_value": officer.jurisdiction_value,
        "jurisdictions": [{"scope_type": s.scope_type, "scope_value": s.scope_value}
                          for s in scopes],
        "reports_to_id": officer.reports_to_id,
        "available": officer.available, "active": officer.active,
        "open_complaints": open_load, "resolved_complaints": resolved,
        "created_at": _iso(officer.created_at),
    }


def complaint_out(db: Session, c: Complaint, detail: bool = False) -> dict:
    dept = db.get(Department, c.department_id) if c.department_id else None
    cat = db.get(Category, c.category_id) if c.category_id else None
    officer = db.get(Officer, c.assigned_officer_id) if c.assigned_officer_id else None

    remaining = None
    overdue = False
    if c.escalation_due_at and c.status in OPEN_STATUSES:
        remaining = int((c.escalation_due_at - datetime.utcnow()).total_seconds() // 60)
        overdue = remaining < 0

    data = {
        "id": c.id, "ticket_ref": c.ticket_ref,
        "department_id": c.department_id, "department": dept.name if dept else None,
        "category_id": c.category_id, "category": cat.name if cat else None,
        "severity": c.severity, "description": c.description,
        "status": c.status, "level": c.level,
        "assigned_officer_id": c.assigned_officer_id,
        "assigned_officer": officer.full_name if officer else None,
        "lat": c.lat, "lon": c.lon, "map_link": c.map_link,
        "area": c.area, "ward": c.ward, "village": c.village, "block": c.block,
        "pincode": c.pincode,
        "created_at": _iso(c.created_at), "acknowledged_at": _iso(c.acknowledged_at),
        "resolved_at": _iso(c.resolved_at), "closed_at": _iso(c.closed_at),
        "escalation_due_at": _iso(c.escalation_due_at),
        "minutes_remaining": remaining, "overdue": overdue,
        "escalation_count": c.escalation_count,
        "reopened_count": c.reopened_count,
        "resolution_verification": c.resolution_verification,
        "group_id": c.group_id, "ai_confidence": c.ai_confidence,
        "sla_paused": c.sla_paused_at is not None,
    }
    if detail:
        images = db.query(ComplaintImage).filter(ComplaintImage.complaint_id == c.id).all()
        data["images"] = [{"kind": i.kind, "telegram_file_id": i.telegram_file_id,
                           "sha256": i.sha256} for i in images]
        data["history"] = [{"action": h.action, "actor_type": h.actor_type,
                            "actor_id": h.actor_id, "from_level": h.from_level,
                            "to_level": h.to_level, "note": h.note,
                            "at": _iso(h.created_at)}
                           for h in (db.query(ComplaintHistory)
                                     .filter(ComplaintHistory.complaint_id == c.id)
                                     .order_by(ComplaintHistory.created_at.asc()).all())]
        data["escalations"] = [{"from_level": e.from_level, "to_level": e.to_level,
                                "reason": e.reason, "automatic": e.automatic,
                                "at": _iso(e.created_at)}
                               for e in (db.query(EscalationHistory)
                                         .filter(EscalationHistory.complaint_id == c.id)
                                         .order_by(EscalationHistory.created_at.asc()).all())]
        data["feedback"] = [{"rating": f.rating, "comment": f.comment,
                             "confirmed": f.resolution_confirmed, "at": _iso(f.created_at)}
                            for f in (db.query(CitizenFeedback)
                                      .filter(CitizenFeedback.complaint_id == c.id)
                                      .order_by(CitizenFeedback.created_at.asc()).all())]
    return data


# ----------------------------------------------------------------------- meta
@router.get("/me")
def me(principal: Principal = Depends(get_principal)):
    return {"username": principal.username, "role": principal.role,
            "is_admin": principal.is_admin, "officer_id": principal.officer_id,
            "department_id": principal.department_id, "level": principal.level}


# ---------------------------------------------------------------- departments
@router.get("/departments")
def list_departments(db: Session = Depends(get_session),
                     principal: Principal = Depends(get_principal)):
    return [department_out(db, d) for d in db.query(Department).order_by(Department.code).all()]


@router.post("/departments", status_code=201)
def create_department(payload: DepartmentIn, db: Session = Depends(get_session),
                      principal: Principal = Depends(require_superadmin)):
    if db.query(Department.id).filter(Department.code == payload.code.upper()).first():
        raise HTTPException(409, "Department code already exists")
    dept = Department(code=payload.code.upper(), name=payload.name,
                      description=payload.description, active=payload.active)
    db.add(dept)
    db.flush()
    db.add(EscalationRule(department_id=dept.id))
    log_action(db, "department.create", actor_type="admin", actor_id=principal.username,
               entity="department", entity_id=dept.id, detail={"code": dept.code})
    db.commit()
    return department_out(db, dept)


@router.patch("/departments/{department_id}")
def update_department(department_id: str, payload: DepartmentIn,
                      db: Session = Depends(get_session),
                      principal: Principal = Depends(require_admin)):
    dept = _dept(db, department_id)
    dept.name = payload.name
    dept.description = payload.description
    dept.active = payload.active
    log_action(db, "department.update", actor_type="admin", actor_id=principal.username,
               entity="department", entity_id=dept.id, detail=payload.model_dump())
    db.commit()
    return department_out(db, dept)


@router.get("/departments/{department_id}/categories")
def list_categories(department_id: str, db: Session = Depends(get_session),
                    principal: Principal = Depends(get_principal)):
    _dept(db, department_id)
    rows = (db.query(Category).filter(Category.department_id == department_id)
            .order_by(Category.name).all())
    return [{"id": c.id, "department_id": c.department_id, "name": c.name,
             "ai_label": c.ai_label, "description": c.description, "active": c.active}
            for c in rows]


@router.post("/categories", status_code=201)
def create_category(payload: CategoryIn, db: Session = Depends(get_session),
                    principal: Principal = Depends(require_admin)):
    _dept(db, payload.department_id)
    if (db.query(Category.id)
            .filter(Category.department_id == payload.department_id,
                    func.lower(Category.name) == payload.name.lower()).first()):
        raise HTTPException(409, "Category already exists for this department")
    cat = Category(department_id=payload.department_id, name=payload.name,
                   ai_label=payload.ai_label or payload.name,
                   description=payload.description, active=payload.active)
    db.add(cat)
    log_action(db, "category.create", actor_type="admin", actor_id=principal.username,
               entity="category", entity_id=cat.id, detail={"name": cat.name})
    db.commit()
    return {"id": cat.id, "name": cat.name, "ai_label": cat.ai_label,
            "department_id": cat.department_id, "active": cat.active}


@router.patch("/categories/{category_id}")
def update_category(category_id: str, payload: CategoryIn,
                    db: Session = Depends(get_session),
                    principal: Principal = Depends(require_admin)):
    cat = db.get(Category, category_id)
    if not cat:
        raise HTTPException(404, "Category not found")
    cat.name = payload.name
    cat.ai_label = payload.ai_label or payload.name
    cat.description = payload.description
    cat.active = payload.active
    log_action(db, "category.update", actor_type="admin", actor_id=principal.username,
               entity="category", entity_id=cat.id, detail=payload.model_dump())
    db.commit()
    return {"id": cat.id, "name": cat.name, "ai_label": cat.ai_label, "active": cat.active}


# ------------------------------------------------------------- escalation rules
@router.get("/escalation-rules")
def list_rules(db: Session = Depends(get_session),
               principal: Principal = Depends(require_admin)):
    rows = db.query(EscalationRule).order_by(EscalationRule.created_at).all()
    return [{"id": r.id, "department_id": r.department_id, "category_id": r.category_id,
             "ack_hours": r.ack_hours, "action_hours": r.action_hours,
             "l1_hours": r.l1_hours, "l2_hours": r.l2_hours, "l3_hours": r.l3_hours,
             "l4_hours": r.l4_hours, "reminder_hours": r.reminder_hours,
             "working_days": r.working_days, "holidays": r.holidays,
             "active": r.active} for r in rows]


@router.put("/escalation-rules/{department_id}")
def upsert_rule(department_id: str, payload: RuleIn, db: Session = Depends(get_session),
                principal: Principal = Depends(require_admin)):
    _dept(db, department_id)
    rule = (db.query(EscalationRule)
            .filter(EscalationRule.department_id == department_id,
                    EscalationRule.category_id.is_(None)).one_or_none())
    if rule is None:
        rule = EscalationRule(department_id=department_id)
        db.add(rule)
    for field, value in payload.model_dump().items():
        setattr(rule, field, value)
    log_action(db, "escalation_rule.upsert", actor_type="admin", actor_id=principal.username,
               entity="department", entity_id=department_id, detail=payload.model_dump())
    db.commit()
    return {"department_id": department_id, **payload.model_dump()}


# -------------------------------------------------------------------- officers
@router.get("/officers")
def list_officers(department_id: Optional[str] = Query(None),
                  level: Optional[int] = Query(None, ge=1, le=4),
                  active: Optional[bool] = Query(None),
                  db: Session = Depends(get_session),
                  principal: Principal = Depends(require_admin)):
    query = db.query(Officer)
    if department_id:
        query = query.filter(Officer.department_id == department_id)
    if level:
        query = query.filter(Officer.level == level)
    if active is not None:
        query = query.filter(Officer.active.is_(active))
    rows = query.order_by(Officer.level, Officer.full_name).all()
    return [officer_out(db, o) for o in rows]


@router.post("/officers", status_code=201)
def create_officer(payload: OfficerIn, db: Session = Depends(get_session),
                   principal: Principal = Depends(require_admin)):
    if payload.department_id:
        _dept(db, payload.department_id)
    officer = Officer(full_name=payload.full_name, designation=payload.designation,
                      department_id=payload.department_id, level=payload.level,
                      employee_code=payload.employee_code, mobile=payload.mobile,
                      email=payload.email, jurisdiction_type=payload.jurisdiction_type,
                      jurisdiction_value=payload.jurisdiction_value,
                      reports_to_id=payload.reports_to_id, available=payload.available,
                      active=payload.active)
    db.add(officer)
    db.flush()
    for scope in payload.jurisdictions:
        db.add(OfficerJurisdiction(officer_id=officer.id, scope_type=scope.scope_type,
                                   scope_value=scope.scope_value))
    log_action(db, "officer.create", actor_type="admin", actor_id=principal.username,
               entity="officer", entity_id=officer.id,
               detail={"name": officer.full_name, "level": officer.level,
                       "department_id": officer.department_id})
    db.commit()
    return officer_out(db, officer)


@router.get("/officers/{officer_id}")
def get_officer(officer_id: str, db: Session = Depends(get_session),
                principal: Principal = Depends(require_admin)):
    return officer_out(db, _officer(db, officer_id))


@router.patch("/officers/{officer_id}")
def update_officer(officer_id: str, payload: OfficerPatch,
                   db: Session = Depends(get_session),
                   principal: Principal = Depends(require_admin)):
    officer = _officer(db, officer_id)
    changes = payload.model_dump(exclude_unset=True)
    if "department_id" in changes and changes["department_id"]:
        _dept(db, changes["department_id"])
    for field, value in changes.items():
        setattr(officer, field, value)
    log_action(db, "officer.update", actor_type="admin", actor_id=principal.username,
               entity="officer", entity_id=officer.id, detail=changes)
    db.commit()
    return officer_out(db, officer)


@router.post("/officers/{officer_id}/invitation", status_code=201)
def invite_officer(officer_id: str, payload: InvitationIn,
                   db: Session = Depends(get_session),
                   principal: Principal = Depends(require_admin)):
    """One-time, expiring code the officer sends to the Telegram bot."""
    officer = _officer(db, officer_id)
    invitation = service.create_invitation(db, officer, principal.username, payload.ttl_hours)
    return {"code": invitation.code, "officer_id": officer.id,
            "officer": officer.full_name, "expires_at": _iso(invitation.expires_at),
            "instructions": ("Ask the officer to open the officer bot, send /start and then "
                             f"paste: {invitation.code}")}


@router.post("/officers/{officer_id}/revoke-telegram")
def revoke_telegram(officer_id: str, db: Session = Depends(get_session),
                    principal: Principal = Depends(require_admin)):
    officer = _officer(db, officer_id)
    service.revoke_telegram_access(db, officer, "revoked by administrator", principal.username)
    return {"ok": True, "officer_id": officer.id, "telegram_connected": False}


@router.get("/officers/{officer_id}/codes")
def officer_codes(officer_id: str, db: Session = Depends(get_session),
                  principal: Principal = Depends(require_admin)):
    _officer(db, officer_id)
    rows = (db.query(InvitationCode).filter(InvitationCode.officer_id == officer_id)
            .order_by(InvitationCode.created_at.desc()).limit(20).all())
    return [{"code": r.code, "expires_at": _iso(r.expires_at), "used_at": _iso(r.used_at),
             "revoked_at": _iso(r.revoked_at)} for r in rows]


# ----------------------------------------------------------------- complaints
@router.get("/complaints")
def list_complaints(status: Optional[str] = Query(None),
                    department_id: Optional[str] = Query(None),
                    category_id: Optional[str] = Query(None),
                    level: Optional[int] = Query(None, ge=1, le=4),
                    officer_id: Optional[str] = Query(None),
                    overdue: Optional[bool] = Query(None),
                    search: Optional[str] = Query(None),
                    limit: int = Query(100, ge=1, le=500),
                    offset: int = Query(0, ge=0),
                    db: Session = Depends(get_session),
                    principal: Principal = Depends(require_admin)):
    query = db.query(Complaint)
    if status:
        query = query.filter(Complaint.status == status.upper())
    if department_id:
        query = query.filter(Complaint.department_id == department_id)
    if category_id:
        query = query.filter(Complaint.category_id == category_id)
    if level:
        query = query.filter(Complaint.level == level)
    if officer_id:
        query = query.filter(Complaint.assigned_officer_id == officer_id)
    if overdue:
        query = query.filter(Complaint.status.in_(OPEN_STATUSES),
                             Complaint.escalation_due_at.isnot(None),
                             Complaint.escalation_due_at < datetime.utcnow())
    if search:
        like = f"%{search}%"
        query = query.filter(func.coalesce(Complaint.ticket_ref, "").like(like)
                             | func.coalesce(Complaint.description, "").like(like)
                             | func.coalesce(Complaint.area, "").like(like))
    total = query.count()
    rows = query.order_by(Complaint.created_at.desc()).offset(offset).limit(limit).all()
    return {"total": total, "limit": limit, "offset": offset,
            "items": [complaint_out(db, c) for c in rows]}


@router.get("/complaints/{complaint_id}")
def get_complaint(complaint_id: str, db: Session = Depends(get_session),
                  principal: Principal = Depends(require_admin)):
    return complaint_out(db, _complaint(db, complaint_id), detail=True)


@router.post("/complaints/{complaint_id}/assign")
def assign_complaint(complaint_id: str, payload: AssignIn,
                     db: Session = Depends(get_session),
                     principal: Principal = Depends(require_admin)):
    complaint = _complaint(db, complaint_id)
    officer = _officer(db, payload.officer_id) if payload.officer_id else None
    escalation.assign(db, complaint, officer, actor_type="admin",
                      actor_id=principal.username,
                      reason=payload.reason or "manual assignment by administrator")
    return complaint_out(db, complaint)


@router.post("/complaints/{complaint_id}/acknowledge")
def acknowledge_complaint(complaint_id: str, db: Session = Depends(get_session),
                          principal: Principal = Depends(require_admin)):
    complaint = _complaint(db, complaint_id)
    officer = db.get(Officer, complaint.assigned_officer_id) if complaint.assigned_officer_id else None
    if not officer:
        raise HTTPException(409, "Complaint has no assigned officer")
    service.acknowledge(db, complaint, officer)
    return complaint_out(db, complaint)


@router.post("/complaints/{complaint_id}/progress")
def progress_complaint(complaint_id: str, payload: NoteIn,
                       db: Session = Depends(get_session),
                       principal: Principal = Depends(require_admin)):
    complaint = _complaint(db, complaint_id)
    officer = db.get(Officer, complaint.assigned_officer_id) if complaint.assigned_officer_id else None
    if not officer:
        raise HTTPException(409, "Complaint has no assigned officer")
    service.mark_in_progress(db, complaint, officer, payload.note)
    return complaint_out(db, complaint)


@router.post("/complaints/{complaint_id}/escalate")
def manual_escalate(complaint_id: str, payload: NoteIn,
                    db: Session = Depends(get_session),
                    principal: Principal = Depends(require_admin)):
    complaint = _complaint(db, complaint_id)
    rule = escalation.get_rule(db, complaint.department_id, complaint.category_id)
    before = complaint.level
    escalation._escalate(db, complaint, rule, datetime.utcnow())
    log_action(db, "complaint.manual_escalate", actor_type="admin",
               actor_id=principal.username, entity="complaint", entity_id=complaint.id,
               detail={"from_level": before, "to_level": complaint.level,
                       "note": payload.note})
    return complaint_out(db, complaint, detail=True)


@router.post("/complaints/{complaint_id}/pause")
def pause_complaint(complaint_id: str, payload: PauseIn,
                    db: Session = Depends(get_session),
                    principal: Principal = Depends(require_admin)):
    complaint = _complaint(db, complaint_id)
    escalation.pause_sla(db, complaint, payload.reason, principal.username)
    return complaint_out(db, complaint)


@router.post("/complaints/{complaint_id}/resume")
def resume_complaint(complaint_id: str, db: Session = Depends(get_session),
                     principal: Principal = Depends(require_admin)):
    complaint = _complaint(db, complaint_id)
    escalation.resume_sla(db, complaint, principal.username)
    return complaint_out(db, complaint)


@router.post("/complaints/{complaint_id}/resolve")
def resolve_complaint(complaint_id: str, payload: ResolveIn,
                      db: Session = Depends(get_session),
                      principal: Principal = Depends(require_admin)):
    complaint = _complaint(db, complaint_id)
    result = service.resolve(db, complaint, notes=payload.notes, actor_type="admin",
                             actor_id=principal.username,
                             run_verification=payload.run_verification)
    return complaint_out(db, result["complaint"], detail=True)


@router.post("/complaints/{complaint_id}/reopen")
def reopen_complaint(complaint_id: str, payload: NoteIn,
                     db: Session = Depends(get_session),
                     principal: Principal = Depends(require_admin)):
    complaint = _complaint(db, complaint_id)
    service.reopen(db, complaint, reason=payload.note or "reopened by administrator",
                   actor_type="admin", actor_id=principal.username)
    return complaint_out(db, complaint)


@router.post("/complaints/{complaint_id}/feedback")
def record_feedback(complaint_id: str, payload: FeedbackIn,
                    db: Session = Depends(get_session),
                    principal: Principal = Depends(require_admin)):
    """Record a citizen's confirmation on their behalf (call-centre workflow)."""
    complaint = _complaint(db, complaint_id)
    service.citizen_feedback(db, complaint, confirmed=payload.confirmed,
                             rating=payload.rating, comment=payload.comment)
    return complaint_out(db, complaint)


# ------------------------------------------------------------ escalation centre
@router.get("/escalation-centre")
def escalation_centre(db: Session = Depends(get_session),
                      principal: Principal = Depends(require_admin)):
    """Everything an L3/L4 authority needs on one screen."""
    now = datetime.utcnow()
    open_rows = db.query(Complaint).filter(Complaint.status.in_(OPEN_STATUSES)).all()

    def bucket(level: int):
        return [complaint_out(db, c) for c in open_rows if c.level == level]

    overdue = [complaint_out(db, c) for c in open_rows
               if c.escalation_due_at and c.escalation_due_at < now]
    unacknowledged = [complaint_out(db, c) for c in open_rows if c.acknowledged_at is None]
    reopened = [complaint_out(db, c) for c in open_rows if c.reopened_count]
    needs_review = [complaint_out(db, c) for c in
                    db.query(Complaint).filter(Complaint.status == "NEEDS_REVIEW").all()]

    return {
        "counts": {
            "l1": len(bucket(1)), "l2": len(bucket(2)),
            "l3": len(bucket(3)), "l4": len(bucket(4)),
            "overdue": len(overdue), "unacknowledged": len(unacknowledged),
            "reopened": len(reopened), "needs_review": len(needs_review),
            "open_total": len(open_rows),
        },
        "pending_l1": bucket(1)[:100],
        "pending_l2": bucket(2)[:100],
        "pending_l3": bucket(3)[:100],
        "pending_l4": bucket(4)[:100],
        "overdue": overdue[:100],
        "unacknowledged": unacknowledged[:100],
        "reopened": reopened[:100],
        "needs_review": needs_review[:100],
    }


# -------------------------------------------------------------------- analytics
@router.get("/analytics/overview")
def analytics_overview(db: Session = Depends(get_session),
                       principal: Principal = Depends(require_admin)):
    now = datetime.utcnow()
    all_rows = db.query(Complaint).all()

    def count(predicate):
        return sum(1 for c in all_rows if predicate(c))

    resolved = [c for c in all_rows if c.resolved_at]
    avg_hours = (sum((c.resolved_at - c.created_at).total_seconds() / 3600 for c in resolved)
                 / len(resolved)) if resolved else 0.0

    per_dept = []
    for dept in db.query(Department).order_by(Department.code).all():
        rows = [c for c in all_rows if c.department_id == dept.id]
        done = [c for c in rows if c.resolved_at]
        per_dept.append({
            "department_id": dept.id, "department": dept.name, "code": dept.code,
            "total": len(rows),
            "open": sum(1 for c in rows if c.status in OPEN_STATUSES),
            "resolved": len(done),
            "escalated": sum(1 for c in rows if c.escalation_count),
            "overdue": sum(1 for c in rows
                           if c.status in OPEN_STATUSES and c.escalation_due_at
                           and c.escalation_due_at < now),
            "avg_resolution_hours": round(
                (sum((c.resolved_at - c.created_at).total_seconds() / 3600 for c in done)
                 / len(done)) if done else 0.0, 2),
        })

    return {
        "total": len(all_rows),
        "new": count(lambda c: c.status == "NEW"),
        "pending": count(lambda c: c.status in OPEN_STATUSES),
        "resolved": count(lambda c: c.status in ("RESOLVED", "VERIFIED", "CLOSED")),
        "closed": count(lambda c: c.status == "CLOSED"),
        "overdue": count(lambda c: c.status in OPEN_STATUSES and c.escalation_due_at
                         and c.escalation_due_at < now),
        "escalated": count(lambda c: c.escalation_count > 0),
        "needs_review": count(lambda c: c.status == "NEEDS_REVIEW"),
        "reopened": count(lambda c: c.reopened_count > 0),
        "unacknowledged": count(lambda c: c.status in OPEN_STATUSES and c.acknowledged_at is None),
        "avg_resolution_hours": round(avg_hours, 2),
        "departments": per_dept,
    }


@router.get("/analytics/officers")
def analytics_officers(db: Session = Depends(get_session),
                       principal: Principal = Depends(require_admin)):
    now = datetime.utcnow()
    result = []
    for officer in db.query(Officer).filter(Officer.active.is_(True)).all():
        rows = db.query(Complaint).filter(Complaint.assigned_officer_id == officer.id).all()
        done = [c for c in rows if c.resolved_at]
        ack_seconds = [(c.acknowledged_at - c.created_at).total_seconds()
                       for c in rows if c.acknowledged_at]
        result.append({
            "officer_id": officer.id, "officer": officer.full_name, "level": officer.level,
            "department_id": officer.department_id,
            "assigned": len(rows),
            "open": sum(1 for c in rows if c.status in OPEN_STATUSES),
            "resolved": len(done),
            "escalated": sum(1 for c in rows if c.escalation_count),
            "reopened": sum(1 for c in rows if c.reopened_count),
            "overdue": sum(1 for c in rows if c.status in OPEN_STATUSES
                           and c.escalation_due_at and c.escalation_due_at < now),
            "avg_ack_hours": round(sum(ack_seconds) / len(ack_seconds) / 3600, 2) if ack_seconds else None,
            "avg_resolution_hours": round(
                sum((c.resolved_at - c.created_at).total_seconds() / 3600 for c in done)
                / len(done), 2) if done else None,
        })
    result.sort(key=lambda x: x["open"], reverse=True)
    return result


@router.get("/analytics/geo")
def analytics_geo(department_id: Optional[str] = Query(None),
                  status: Optional[str] = Query(None),
                  severity: Optional[str] = Query(None),
                  level: Optional[int] = Query(None, ge=1, le=4),
                  db: Session = Depends(get_session),
                  principal: Principal = Depends(get_principal)):
    query = db.query(Complaint).filter(Complaint.lat.isnot(None), Complaint.lon.isnot(None))
    if department_id:
        query = query.filter(Complaint.department_id == department_id)
    if status:
        query = query.filter(Complaint.status == status.upper())
    if severity:
        query = query.filter(Complaint.severity == severity.title())
    if level:
        query = query.filter(Complaint.level == level)

    now = datetime.utcnow()
    points = []
    for c in query.all():
        dept = db.get(Department, c.department_id) if c.department_id else None
        cat = db.get(Category, c.category_id) if c.category_id else None
        points.append({"id": c.id, "ticket_ref": c.ticket_ref, "lat": c.lat, "lon": c.lon,
                       "department_id": c.department_id,
                       "department": dept.name if dept else None,
                       "category": cat.name if cat else None,
                       "severity": c.severity, "status": c.status, "level": c.level,
                       "overdue": bool(c.escalation_due_at and c.status in OPEN_STATUSES
                                       and c.escalation_due_at < now),
                       "group_id": c.group_id})
    return {"count": len(points), "points": points}


# ---------------------------------------------------------------------- reports
@router.get("/reports/complaints")
def report_complaints(format: str = Query("csv", pattern="^(csv|xlsx)$"),
                      department_id: Optional[str] = Query(None),
                      date_from: Optional[str] = Query(None),
                      date_to: Optional[str] = Query(None),
                      db: Session = Depends(get_session),
                      principal: Principal = Depends(require_admin)):
    """Daily/weekly/monthly export - filter by department and date range."""
    query = db.query(Complaint)
    if department_id:
        query = query.filter(Complaint.department_id == department_id)
    if date_from:
        query = query.filter(Complaint.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.filter(Complaint.created_at <= datetime.fromisoformat(date_to))
    rows = query.order_by(Complaint.created_at.desc()).all()

    headers = ["Ticket", "Created", "Department", "Category", "Severity", "Status", "Level",
               "Officer", "Area", "Pincode", "Escalations", "Reopened", "Resolved",
               "Verification"]
    records = []
    for c in rows:
        dept = db.get(Department, c.department_id) if c.department_id else None
        cat = db.get(Category, c.category_id) if c.category_id else None
        officer = db.get(Officer, c.assigned_officer_id) if c.assigned_officer_id else None
        records.append([c.ticket_ref, c.created_at.strftime("%Y-%m-%d %H:%M"),
                        dept.name if dept else "", cat.name if cat else "", c.severity,
                        c.status, f"L{c.level}", officer.full_name if officer else "",
                        c.area, c.pincode, c.escalation_count, c.reopened_count,
                        c.resolved_at.strftime("%Y-%m-%d %H:%M") if c.resolved_at else "",
                        c.resolution_verification])

    log_action(db, "report.export", actor_type="admin", actor_id=principal.username,
               entity="complaint", detail={"format": format, "rows": len(records)})
    db.commit()

    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M")

    if format == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(headers)
        writer.writerows(records)
        payload = io.BytesIO(buffer.getvalue().encode("utf-8-sig"))
        media = "text/csv"
        filename = f"complaints-{stamp}.csv"
    else:
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Complaints"
        ws.append(headers)
        for record in records:
            ws.append(record)
        for column, width in zip("ABCDEFGHIJKLMN",
                                 (16, 17, 26, 22, 10, 14, 7, 24, 18, 10, 11, 9, 17, 13)):
            ws.column_dimensions[column].width = width
        payload = io.BytesIO()
        wb.save(payload)
        payload.seek(0)
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"complaints-{stamp}.xlsx"

    return StreamingResponse(payload, media_type=media,
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ------------------------------------------------------------------- audit logs
@router.get("/audit-logs")
def audit_logs(limit: int = Query(200, ge=1, le=1000),
               entity: Optional[str] = Query(None),
               entity_id: Optional[str] = Query(None),
               db: Session = Depends(get_session),
               principal: Principal = Depends(require_admin)):
    from core.models import AuditLog
    query = db.query(AuditLog)
    if entity:
        query = query.filter(AuditLog.entity == entity)
    if entity_id:
        query = query.filter(AuditLog.entity_id == entity_id)
    rows = query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    return [{"id": r.id, "action": r.action, "actor_type": r.actor_type,
             "actor_id": r.actor_id, "entity": r.entity, "entity_id": r.entity_id,
             "detail": r.detail, "at": _iso(r.created_at)} for r in rows]


# ------------------------------------------------------------- admin accounts
@router.get("/admins")
def list_admins(db: Session = Depends(get_session),
                principal: Principal = Depends(require_superadmin)):
    from core.models import AdminUser
    return [{"id": u.id, "username": u.username, "role": u.role, "active": u.active,
             "created_at": _iso(u.created_at)}
            for u in db.query(AdminUser).order_by(AdminUser.username).all()]


@router.post("/admins", status_code=201)
def create_admin(payload: AdminIn, db: Session = Depends(get_session),
                 principal: Principal = Depends(require_superadmin)):
    from core.models import AdminUser
    if db.query(AdminUser.id).filter(AdminUser.username == payload.username).first():
        raise HTTPException(409, "Username already exists")
    if payload.role not in ("superadmin", "admin", "viewer"):
        raise HTTPException(400, "role must be superadmin, admin or viewer")
    user = AdminUser(username=payload.username,
                     password_hash=hash_password(payload.password), role=payload.role)
    db.add(user)
    log_action(db, "admin.create", actor_type="admin", actor_id=principal.username,
               entity="admin_user", entity_id=user.id,
               detail={"username": user.username, "role": user.role})
    db.commit()
    return {"id": user.id, "username": user.username, "role": user.role}


@router.post("/admins/{admin_id}/deactivate")
def deactivate_admin(admin_id: str, db: Session = Depends(get_session),
                     principal: Principal = Depends(require_superadmin)):
    from core.models import AdminUser
    user = db.get(AdminUser, admin_id)
    if not user:
        raise HTTPException(404, "Admin not found")
    if user.username == principal.username:
        raise HTTPException(400, "You cannot deactivate your own account")
    user.active = False
    log_action(db, "admin.deactivate", actor_type="admin", actor_id=principal.username,
               entity="admin_user", entity_id=user.id, detail={"username": user.username})
    db.commit()
    return {"ok": True, "username": user.username, "active": False}










