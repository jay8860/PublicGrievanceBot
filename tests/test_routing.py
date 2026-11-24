"""Geographical routing: ward matching, no-random-assignment, workload balance."""
from core import service
from core.models import Complaint, Officer, OfficerJurisdiction
from core.seed import ensure_seed


def _officer(db, dept_id, name, level=1, jurisdiction_type="district",
             jurisdiction_value="", ward=None, available=True):
    officer = Officer(full_name=name, department_id=dept_id, level=level,
                      jurisdiction_type=jurisdiction_type,
                      jurisdiction_value=jurisdiction_value,
                      available=available, active=True)
    db.add(officer)
    db.flush()
    if ward:
        db.add(OfficerJurisdiction(officer_id=officer.id, scope_type="ward", scope_value=ward))
    db.commit()
    return officer


def test_routes_to_the_officer_of_the_matching_ward(db):
    depts = ensure_seed(db)
    pwd = depts["PWD"]
    ward_a = _officer(db, pwd.id, "Ward A Officer", jurisdiction_type="ward",
                      jurisdiction_value="Ward A", ward="Ward A")
    ward_b = _officer(db, pwd.id, "Ward B Officer", jurisdiction_type="ward",
                      jurisdiction_value="Ward B", ward="Ward B")

    complaint = service.create_complaint(db, citizen_chat_id="c-1", description="Cracked road",
                                         category_label="Road Infra", ward="Ward B")
    assert complaint.assigned_officer_id == ward_b.id
    assert complaint.assigned_officer_id != ward_a.id


def test_unconfigured_department_goes_to_review_instead_of_random_assignment(db):
    ensure_seed(db)      # MUNICIPAL has categories but no officers yet

    complaint = service.create_complaint(db, citizen_chat_id="c-2", description="Garbage pile",
                                         category_label="Sanitation", ward="Ward 4")
    assert complaint.status == "NEEDS_REVIEW"
    assert complaint.assigned_officer_id is None
    assert complaint.escalation_due_at is None


def test_unrecognised_ai_label_is_flagged_not_guessed(db):
    ensure_seed(db)
    complaint = service.create_complaint(db, citizen_chat_id="c-3", description="???",
                                         category_label="Interplanetary Teleport",
                                         ward="Ward 1")
    assert complaint.status == "NEEDS_REVIEW"
    assert complaint.category_id is None


def test_duplicate_reports_are_grouped_but_never_discarded(db):
    depts = ensure_seed(db)
    pwd = depts["PWD"]
    _officer(db, pwd.id, "PWD Officer")

    first = service.create_complaint(db, citizen_chat_id="c-4", description="Pothole",
                                     category_label="Road Infra", lat=20.1000, lon=81.1000)
    second = service.create_complaint(db, citizen_chat_id="c-5", description="Same pothole",
                                      category_label="Road Infra", lat=20.1001, lon=81.1001)
    third = service.create_complaint(db, citizen_chat_id="c-6", description="Far away pothole",
                                     category_label="Road Infra", lat=21.5000, lon=82.5000)

    assert first.id != second.id                       # both submissions preserved
    assert second.group_id == first.id                 # grouped as a duplicate
    assert third.group_id is None                      # far away -> separate
    assert db.query(Complaint).count() == 3


def test_workload_balance_prefers_the_less_loaded_officer(db):
    depts = ensure_seed(db)
    pwd = depts["PWD"]
    busy = _officer(db, pwd.id, "Busy Officer")
    idle = _officer(db, pwd.id, "Idle Officer")

    db.add(Complaint(ticket_ref="GRV-TEST-000900", citizen_chat_id="x",
                     department_id=pwd.id, status="ASSIGNED", level=1,
                     assigned_officer_id=busy.id))
    busy_second = _officer(db, pwd.id, "Busy Officer 2")
    db.add(Complaint(ticket_ref="GRV-TEST-000901", citizen_chat_id="y",
                     department_id=pwd.id, status="IN_PROGRESS", level=1,
                     assigned_officer_id=busy_second.id))
    db.commit()

    complaint = service.create_complaint(db, citizen_chat_id="c-7", description="Pothole",
                                         category_label="Road Infra")
    # busy has 1 open, busy_second has 1 open, idle has 0 -> idle wins
    assert complaint.assigned_officer_id == idle.id
