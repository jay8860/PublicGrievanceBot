"""TAT engine: automatic L1->L4 escalation, dedupe, reminders, no auto-close."""
from datetime import datetime, timedelta

from core import escalation, service
from core.models import Complaint, EscalationHistory, Notification, Officer
from core.seed import ensure_seed


def _pwd_with_l1_to_l4(db):
    depts = ensure_seed(db)
    pwd = depts["PWD"]
    officers = []
    for level in (1, 2, 3, 4):
        officer = Officer(full_name=f"PWD L{level}", department_id=pwd.id, level=level,
                          jurisdiction_type="district", jurisdiction_value="Dhamtari",
                          telegram_chat_id=str(9000 + level), active=True, available=True)
        db.add(officer)
        officers.append(officer)
    db.commit()
    return pwd, officers


def _new_complaint(db, **kwargs):
    payload = dict(citizen_chat_id="citizen-1", description="Large pothole near school",
                   category_label="Road Infra", severity="High",
                   lat=20.1, lon=81.1, area="Ward 5", ward="Ward 5")
    payload.update(kwargs)
    return service.create_complaint(db, **payload)


def test_new_complaint_is_routed_to_l1_with_a_deadline(db):
    _, officers = _pwd_with_l1_to_l4(db)
    complaint = _new_complaint(db)

    assert complaint.status == "ASSIGNED"
    assert complaint.level == 1
    assert complaint.assigned_officer_id == officers[0].id
    assert complaint.escalation_due_at is not None
    assert complaint.ticket_ref.startswith("GRV-")


def test_escalates_l1_l2_l3_l4_and_never_auto_closes(db):
    _, officers = _pwd_with_l1_to_l4(db)
    complaint = _new_complaint(db)
    original_ref = complaint.ticket_ref

    # L1 TAT expires -> L2
    db.refresh(complaint)
    first_tick = complaint.escalation_due_at + timedelta(minutes=1)
    summary = escalation.run_once(db, now=first_tick)
    assert summary["escalations"] == 1
    db.refresh(complaint)
    assert complaint.level == 2
    assert complaint.status == "ESCALATED"
    assert complaint.assigned_officer_id == officers[1].id
    assert complaint.ticket_ref == original_ref          # original ID preserved

    # A second tick at the same instant must not double-escalate.
    again = escalation.run_once(db, now=first_tick)
    db.refresh(complaint)
    assert again["escalations"] == 0
    assert complaint.level == 2
    assert db.query(EscalationHistory).filter_by(complaint_id=complaint.id).count() == 1

    # L2 -> L3
    escalation.run_once(db, now=complaint.escalation_due_at + timedelta(minutes=1))
    db.refresh(complaint)
    assert complaint.level == 3

    # L3 -> L4
    escalation.run_once(db, now=complaint.escalation_due_at + timedelta(minutes=1))
    db.refresh(complaint)
    assert complaint.level == 4
    assert complaint.escalation_count == 3

    # L4 overdue: alert only - the complaint must not be resolved/closed.
    escalation.run_once(db, now=complaint.escalation_due_at + timedelta(minutes=1))
    db.refresh(complaint)
    assert complaint.level == 4
    assert complaint.status == "ESCALATED"
    assert complaint.escalation_due_at is None
    assert complaint.resolved_at is None and complaint.closed_at is None


def test_reminder_is_sent_once_before_the_deadline(db):
    _pwd_with_l1_to_l4(db)
    complaint = _new_complaint(db)
    db.refresh(complaint)

    window = complaint.escalation_due_at - timedelta(hours=5)   # rule reminder = 6h
    first = escalation.run_once(db, now=window)
    assert first["reminders"] == 1

    second = escalation.run_once(db, now=window + timedelta(minutes=1))
    assert second["reminders"] == 0
    assert db.query(Notification).filter_by(complaint_id=complaint.id,
                                            kind="reminder").count() == 1


def test_paused_sla_is_not_escalated_and_resume_shifts_deadline(db):
    _pwd_with_l1_to_l4(db)
    complaint = _new_complaint(db)
    db.refresh(complaint)

    escalation.pause_sla(db, complaint, "awaiting citizen clarification", "admin")
    db.refresh(complaint)
    assert complaint.sla_paused_at is not None
    escalated = escalation.run_once(db, now=complaint.escalation_due_at + timedelta(hours=2))
    assert escalated["escalations"] == 0
    assert complaint.level == 1

    escalation.resume_sla(db, complaint, "admin")
    db.refresh(complaint)
    assert complaint.sla_paused_at is None
    assert complaint.escalation_due_at is not None


def test_manual_assignment_leaves_needs_review(db):
    """Regression: legacy rows carry acknowledged_at, so assignment must still
    move a NEEDS_REVIEW complaint to ASSIGNED (and adopt the department)."""
    depts = ensure_seed(db)
    municipal = depts["MUNICIPAL"]
    officer = Officer(full_name="Municipal L1", department_id=municipal.id, level=1,
                      jurisdiction_type="district", active=True, available=True)
    db.add(officer)
    complaint = Complaint(ticket_ref="GRV-TEST-000777", citizen_chat_id="legacy",
                          status="NEEDS_REVIEW", level=1,
                          acknowledged_at=datetime.utcnow())
    db.add(complaint)
    db.commit()

    escalation.assign(db, complaint, officer, actor_type="admin", actor_id="tester",
                      reason="manual")
    db.refresh(complaint)

    assert complaint.status == "ASSIGNED"
    assert complaint.department_id == municipal.id          # adopted from the officer
    assert complaint.assigned_officer_id == officer.id
    assert complaint.escalation_due_at is not None

    _, officers = _pwd_with_l1_to_l4(db)
    complaint = _new_complaint(db)
    rule = escalation.get_rule(db, complaint.department_id, complaint.category_id)

    escalation._escalate(db, complaint, rule, complaint.created_at + timedelta(minutes=5))
    db.refresh(complaint)

    assert complaint.level == 2
    history = db.query(EscalationHistory).filter_by(complaint_id=complaint.id).all()
    assert len(history) == 1
    assert history[0].automatic is True
    assert history[0].from_level == 1 and history[0].to_level == 2
    assert complaint.escalation_count == 1
