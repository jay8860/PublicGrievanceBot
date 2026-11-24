"""SQLAlchemy models: departments, officers, complaints, escalation, audit.

Design notes
------------
* String UUID primary keys generated in Python, so SQLite and PostgreSQL behave
  identically and IDs stay globally unique.
* ``Complaint.escalation_due_at`` is the single source of truth the background
  worker polls, which keeps the TAT engine independent of the dashboard and
  restart-safe (deadlines live in the database, not in memory).
* Google Sheets stays untouched - this is an additive store.
"""
import uuid
from datetime import datetime

from sqlalchemy import (JSON, Boolean, Column, DateTime, Float, ForeignKey,
                        Index, Integer, String, Text, UniqueConstraint)

from .db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.utcnow()


# ---------------------------------------------------------------- departments
class Department(Base):
    __tablename__ = "departments"

    id = Column(String(32), primary_key=True, default=_uuid)
    code = Column(String(32), unique=True, nullable=False)          # e.g. MUNICIPAL
    name = Column(String(120), nullable=False)
    description = Column(Text, default="")
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=_now, nullable=False)

    __table_args__ = (Index("ix_departments_code", "code"),)


class Category(Base):
    __tablename__ = "complaint_categories"

    id = Column(String(32), primary_key=True, default=_uuid)
    department_id = Column(String(32), ForeignKey("departments.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(120), nullable=False)
    description = Column(Text, default="")
    ai_label = Column(String(80), default="")      # what the AI is asked to return
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("department_id", "name", name="uq_category_dept_name"),
        Index("ix_categories_dept", "department_id"),
    )


# -------------------------------------------------------------------- officers
class Officer(Base):
    __tablename__ = "officers"

    id = Column(String(32), primary_key=True, default=_uuid)
    employee_code = Column(String(40), default="")
    full_name = Column(String(120), nullable=False)
    designation = Column(String(120), default="")
    department_id = Column(String(32), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    level = Column(Integer, nullable=False, default=1)               # 1..4 logical escalation level
    mobile = Column(String(20), default="")
    email = Column(String(120), default="")

    # A Telegram account can only ever be linked to one officer.
    telegram_chat_id = Column(String(32), unique=True, nullable=True)
    telegram_linked_at = Column(DateTime, nullable=True)
    telegram_revoked_at = Column(DateTime, nullable=True)

    jurisdiction_type = Column(String(20), default="district")      # district|block|ward|village
    jurisdiction_value = Column(String(120), default="")

    reports_to_id = Column(String(32), ForeignKey("officers.id", ondelete="SET NULL"), nullable=True)
    available = Column(Boolean, default=True, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=_now, nullable=False)

    __table_args__ = (
        Index("ix_officers_dept_level", "department_id", "level"),
        Index("ix_officers_chat", "telegram_chat_id"),
    )


class OfficerJurisdiction(Base):
    """One officer can cover several wards/blocks/villages."""
    __tablename__ = "officer_jurisdictions"

    id = Column(String(32), primary_key=True, default=_uuid)
    officer_id = Column(String(32), ForeignKey("officers.id", ondelete="CASCADE"), nullable=False)
    scope_type = Column(String(20), nullable=False)                 # block|ward|village|district
    scope_value = Column(String(120), nullable=False)

    __table_args__ = (
        UniqueConstraint("officer_id", "scope_type", "scope_value", name="uq_officer_scope"),
        Index("ix_jurisdiction_lookup", "scope_type", "scope_value"),
    )


class TelegramMapping(Base):
    """Audit trail of chat_id <-> officer link/unlink events."""
    __tablename__ = "telegram_mappings"

    id = Column(String(32), primary_key=True, default=_uuid)
    chat_id = Column(String(32), nullable=False)
    officer_id = Column(String(32), ForeignKey("officers.id", ondelete="CASCADE"), nullable=False)
    linked_at = Column(DateTime, default=_now, nullable=False)
    unlinked_at = Column(DateTime, nullable=True)
    unlinked_reason = Column(String(200), default="")

    __table_args__ = (Index("ix_tg_map_chat", "chat_id"),)


class InvitationCode(Base):
    __tablename__ = "invitation_codes"

    id = Column(String(32), primary_key=True, default=_uuid)
    code = Column(String(24), unique=True, nullable=False)
    officer_id = Column(String(32), ForeignKey("officers.id", ondelete="CASCADE"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    used_by_chat_id = Column(String(32), nullable=True)
    created_by = Column(String(120), default="")
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now, nullable=False)

    __table_args__ = (Index("ix_invite_code", "code"),)


class AdminUser(Base):
    """Individual admin accounts (RBAC). Legacy env admin is bootstrapped here."""
    __tablename__ = "admin_users"

    id = Column(String(32), primary_key=True, default=_uuid)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="admin", nullable=False)      # superadmin|admin|viewer
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=_now, nullable=False)


# ------------------------------------------------------------------ escalation
class EscalationRule(Base):
    """Per-department (optionally per-category) TAT configuration, in hours."""
    __tablename__ = "escalation_rules"

    id = Column(String(32), primary_key=True, default=_uuid)
    department_id = Column(String(32), ForeignKey("departments.id", ondelete="CASCADE"), nullable=False)
    category_id = Column(String(32), ForeignKey("complaint_categories.id", ondelete="CASCADE"), nullable=True)

    ack_hours = Column(Integer, default=12, nullable=False)          # L1 must acknowledge
    action_hours = Column(Integer, default=24, nullable=False)       # first action
    l1_hours = Column(Integer, default=48, nullable=False)           # L1 resolution window
    l2_hours = Column(Integer, default=24, nullable=False)
    l3_hours = Column(Integer, default=24, nullable=False)
    l4_hours = Column(Integer, default=48, nullable=False)           # final administrative review
    reminder_hours = Column(Integer, default=6, nullable=False)      # reminder before deadline
    working_days = Column(JSON, default=lambda: [0, 1, 2, 3, 4, 5])  # Mon..Sat
    holidays = Column(JSON, default=list)                            # ["2026-01-26", ...]
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=_now, nullable=False)

    __table_args__ = (Index("ix_rules_dept", "department_id"),)

    def hours_for_level(self, level: int) -> int:
        value = {1: self.l1_hours, 2: self.l2_hours, 3: self.l3_hours}.get(level, self.l4_hours)
        return value if value is not None else 48


# ------------------------------------------------------------------ complaints
class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(String(32), primary_key=True, default=_uuid)
    ticket_ref = Column(String(40), unique=True, nullable=False)      # human-facing, e.g. DHM-2026-000123

    citizen_chat_id = Column(String(32), nullable=False)
    citizen_name = Column(String(120), default="")
    citizen_phone = Column(String(20), default="")

    department_id = Column(String(32), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    category_id = Column(String(32), ForeignKey("complaint_categories.id", ondelete="SET NULL"), nullable=True)
    severity = Column(String(12), default="Medium")                   # High|Medium|Low
    description = Column(Text, default="")

    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    accuracy_m = Column(Float, nullable=True)
    pincode = Column(String(12), default="")
    area = Column(String(120), default="")
    block = Column(String(120), default="")
    ward = Column(String(120), default="")
    village = Column(String(120), default="")
    map_link = Column(String(300), default="")

    # NEW|NEEDS_REVIEW|ASSIGNED|ACKNOWLEDGED|IN_PROGRESS|ESCALATED|RESOLVED|VERIFIED|REOPENED|CLOSED
    status = Column(String(20), default="NEW", nullable=False)
    level = Column(Integer, default=1, nullable=False)
    assigned_officer_id = Column(String(32), ForeignKey("officers.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime, default=_now, nullable=False)
    acknowledged_at = Column(DateTime, nullable=True)
    first_action_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)
    escalation_due_at = Column(DateTime, nullable=True, index=True)
    reminder_sent_at = Column(DateTime, nullable=True)

    sla_paused_at = Column(DateTime, nullable=True)
    sla_pause_reason = Column(String(300), default="")
    sla_paused_by = Column(String(120), default="")

    ai_confidence = Column(Float, default=0.0)
    ai_raw = Column(JSON, default=dict)
    integrity_metric = Column(String(40), default="Validated")
    group_id = Column(String(32), nullable=True, index=True)          # duplicate grouping
    reopened_count = Column(Integer, default=0, nullable=False)
    escalation_count = Column(Integer, default=0, nullable=False)
    resolution_verification = Column(String(30), default="")           # verified|manual_review|failed
    resolution_notes = Column(Text, default="")

    __table_args__ = (
        Index("ix_complaints_status_due", "status", "escalation_due_at"),
        Index("ix_complaints_dept_status", "department_id", "status"),
        Index("ix_complaints_officer", "assigned_officer_id"),
        Index("ix_complaints_created", "created_at"),
    )


class ComplaintImage(Base):
    __tablename__ = "complaint_images"

    id = Column(String(32), primary_key=True, default=_uuid)
    complaint_id = Column(String(32), ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False)
    kind = Column(String(20), default="original", nullable=False)     # original|resolution
    storage_key = Column(String(300), default="")                    # S3 key / local path
    url = Column(String(500), default="")
    telegram_file_id = Column(String(200), default="")
    sha256 = Column(String(64), default="")
    created_at = Column(DateTime, default=_now, nullable=False)

    __table_args__ = (Index("ix_images_complaint", "complaint_id", "kind"),)


class ComplaintHistory(Base):
    __tablename__ = "complaint_history"

    id = Column(String(32), primary_key=True, default=_uuid)
    complaint_id = Column(String(32), ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False)
    action = Column(String(40), nullable=False)                       # created|assigned|acknowledged|...
    actor_type = Column(String(20), default="system")                 # citizen|officer|admin|system
    actor_id = Column(String(120), default="")
    from_level = Column(Integer, nullable=True)
    to_level = Column(Integer, nullable=True)
    note = Column(Text, default="")
    created_at = Column(DateTime, default=_now, nullable=False)

    __table_args__ = (Index("ix_history_complaint", "complaint_id", "created_at"),)


class EscalationHistory(Base):
    __tablename__ = "escalation_history"

    id = Column(String(32), primary_key=True, default=_uuid)
    complaint_id = Column(String(32), ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False)
    from_level = Column(Integer, nullable=False)
    to_level = Column(Integer, nullable=False)
    from_officer_id = Column(String(32), nullable=True)
    to_officer_id = Column(String(32), nullable=True)
    reason = Column(String(300), default="")
    automatic = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=_now, nullable=False)
    # Guards against double-escalation if two ticks/workers overlap.
    dedupe_key = Column(String(120), unique=True, nullable=True)

    __table_args__ = (Index("ix_esc_complaint", "complaint_id", "created_at"),)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String(32), primary_key=True, default=_uuid)
    complaint_id = Column(String(32), ForeignKey("complaints.id", ondelete="SET NULL"), nullable=True)
    chat_id = Column(String(32), default="")
    kind = Column(String(40), default="")                             # assigned|reminder|escalated|...
    dedupe_key = Column(String(160), unique=True, nullable=True)
    status = Column(String(20), default="sent")                       # sent|failed|skipped
    error = Column(String(400), default="")
    created_at = Column(DateTime, default=_now, nullable=False)

    __table_args__ = (Index("ix_notifications_complaint", "complaint_id", "kind"),)


class CitizenFeedback(Base):
    __tablename__ = "citizen_feedback"

    id = Column(String(32), primary_key=True, default=_uuid)
    complaint_id = Column(String(32), ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False)
    rating = Column(Integer, nullable=True)                           # 1..5
    comment = Column(Text, default="")
    resolution_confirmed = Column(Boolean, nullable=True)             # True confirm / False still broken
    created_at = Column(DateTime, default=_now, nullable=False)

    __table_args__ = (Index("ix_feedback_complaint", "complaint_id"),)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(32), primary_key=True, default=_uuid)
    actor_type = Column(String(20), default="system")
    actor_id = Column(String(120), default="")
    action = Column(String(60), nullable=False)
    entity = Column(String(40), default="")
    entity_id = Column(String(64), default="")
    detail = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_now, nullable=False)

    __table_args__ = (
        Index("ix_audit_entity", "entity", "entity_id"),
        Index("ix_audit_actor", "actor_type", "actor_id"),
    )


