"""Create a demo dataset for local frontend work (opt-in, never run in prod).

    python scripts/seed_demo.py

Creates officers across all five departments plus complaints in every state so
every dashboard page has real API data to render.
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DATABASE_URL", "sqlite:///./grievance.db")

from core.db import SessionLocal, init_db  # noqa: E402
from core.models import (CitizenFeedback, Complaint, ComplaintHistory,  # noqa: E402
                         ComplaintImage, EscalationHistory, Officer,
                         OfficerJurisdiction)
from core.seed import ensure_seed  # noqa: E402

OFFICERS = [
    ("MUNICIPAL", 1, "Rakesh Verma", "Sanitation Inspector", "Ward 5"),
    ("MUNICIPAL", 2, "Sunita Sahu", "Health Officer", ""),
    ("MUNICIPAL", 3, "A. K. Sharma", "Additional Commissioner", ""),
    ("MUNICIPAL", 4, "Collector Office", "District Collector", ""),
    ("PWD", 1, "Mohan Yadav", "Junior Engineer", "Ward 7"),
    ("PWD", 2, "Kavita Patel", "Executive Engineer", ""),
    ("PWD", 3, "R. N. Tiwari", "Superintending Engineer", ""),
    ("PWD", 4, "Collector Office", "District Collector", ""),
    ("PHE", 1, "Imran Khan", "Assistant Engineer", "Ward 3"),
    ("PHE", 2, "Deepak Soni", "Executive Engineer", ""),
    ("ELECTRICITY", 1, "Sanjay Baghel", "Lineman Supervisor", "Ward 2"),
    ("ELECTRICITY", 2, "Neha Mishra", "Assistant Engineer", ""),
    ("REVENUE", 1, "Pooja Rathore", "Tehsildar", "Block Dhamtari"),
    ("REVENUE", 2, "V. K. Dubey", "Sub-Divisional Officer", ""),
]

# label, severity, description, ward, status, days_ago, level, resolved, verdict, rating
CASES = [
    ("Sanitation", "High", "Overflowing garbage bins near the bus stand", "Ward 5",
     "ASSIGNED", 1, 1, False, "", None),
    ("Sanitation", "Medium", "Garbage not collected for four days in sector 3", "Ward 5",
     "IN_PROGRESS", 3, 1, False, "", None),
    ("Drainage", "High", "Open drain overflowing onto the main road", "Ward 3",
     "ESCALATED", 4, 2, False, "", None),
    ("Lighting", "Medium", "Street light not working since last week", "Ward 2",
     "ACKNOWLEDGED", 2, 1, False, "", None),
    ("Road Infra", "High", "Deep pothole causing two-wheeler accidents", "Ward 7",
     "ESCALATED", 6, 2, False, "", None),
    ("Road Infra", "Medium", "Damaged speed breaker near school gate", "Ward 7",
     "RESOLVED", 8, 1, True, "requires_review", 4),
    ("Water Supply", "High", "Contaminated water supplied in pipeline", "Ward 3",
     "RESOLVED", 5, 1, True, "verified", 5),
    ("Water Supply", "Low", "Low water pressure in the morning hours", "Ward 3",
     "CLOSED", 12, 1, True, "verified", 4),
    ("Power Outage", "High", "Transformer burnt, entire mohalla without power", "Ward 2",
     "IN_PROGRESS", 1, 1, False, "", None),
    ("Power Outage", "Medium", "Frequent power cuts in the evening", "Ward 2",
     "CLOSED", 15, 1, True, "verified", 3),
    ("Land Revenue", "Medium", "Mutation application pending for three months",
     "Block Dhamtari", "NEEDS_REVIEW", 10, 1, False, "", None),
    ("Potholes", "Low", "Small potholes on the colony approach road", "Ward 7",
     "NEW", 0, 1, False, "", None),
]


def _create_officers(db, depts):
    for code, level, name, designation, scope in OFFICERS:
        officer = Officer(
            full_name=name, designation=designation,
            department_id=depts[code].id, level=level,
            employee_code=f"{code[:3]}-L{level}",
            mobile="9" + str(abs(hash(name)) % 10 ** 9).zfill(9),
            email=f"{name.split()[0].lower()}@dhamtari.gov.in",
            jurisdiction_type="ward" if scope.startswith("Ward") else "block",
            jurisdiction_value=scope, active=True, available=True,
        )
        db.add(officer)
        db.flush()
        if scope:
            db.add(OfficerJurisdiction(
                officer_id=officer.id,
                scope_type="ward" if scope.startswith("Ward") else "block",
                scope_value=scope))
    db.commit()


def _create_complaints(db):
    from core.service import resolve_category

    for i, (label, severity, desc, ward, status, days, level, resolved,
            verdict, rating) in enumerate(CASES, start=1):
        category = resolve_category(db, label)
        if not category:
            continue
        created = datetime.utcnow() - timedelta(days=days, hours=i)
        officer = (db.query(Officer)
                   .filter(Officer.department_id == category.department_id,
                           Officer.level == level).first())

        complaint = Complaint(
            ticket_ref=f"GRV-2026-{i:06d}", citizen_chat_id=f"9000000{i:02d}",
            department_id=category.department_id, category_id=category.id,
            severity=severity, description=desc, status=status, level=level,
            lat=20.70 + i * 0.003, lon=81.55 + i * 0.004,
            area=ward, ward=ward, pincode="493773",
            map_link=f"https://www.google.com/maps?q={20.70 + i * 0.003},{81.55 + i * 0.004}",
            assigned_officer_id=officer.id if officer else None,
            created_at=created,
            acknowledged_at=None if status == "NEW" else created + timedelta(hours=2),
            resolved_at=created + timedelta(days=2) if resolved else None,
            escalation_due_at=None if resolved else created + timedelta(hours=48),
            escalation_count=max(0, level - 1),
        )
        db.add(complaint)
        db.flush()
        db.add(ComplaintImage(complaint_id=complaint.id, kind="original", telegram_file_id=""))
        if resolved:
            db.add(ComplaintImage(complaint_id=complaint.id, kind="resolution",
                                  telegram_file_id=""))
            complaint.resolution_verification = verdict
            db.add(CitizenFeedback(complaint_id=complaint.id, rating=rating,
                                   resolution_confirmed=(status == "CLOSED")))
        db.add(ComplaintHistory(complaint_id=complaint.id, action="created",
                                actor_type="citizen", actor_id=complaint.citizen_chat_id))
        if level > 1:
            db.add(EscalationHistory(complaint_id=complaint.id, from_level=1, to_level=level,
                                     reason="TAT expired at L1 without resolution",
                                     automatic=True,
                                     dedupe_key=f"demo-esc-{complaint.id}"))
    db.commit()


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        depts = ensure_seed(db)
        if db.query(Officer).count() == 0:
            _create_officers(db, depts)
        if db.query(Complaint).count() == 0:
            _create_complaints(db)
        print(f"Demo data ready: {db.query(Officer).count()} officers, "
              f"{db.query(Complaint).count()} complaints")
    finally:
        db.close()


if __name__ == "__main__":
    main()

