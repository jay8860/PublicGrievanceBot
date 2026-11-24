"""One-off migration: Google Sheets -> platform database.

* Non-destructive: never deletes or edits the spreadsheet, never overwrites an
  existing complaint (idempotent on ticket ref).
* Preserves legacy ticket IDs, citizen chat IDs, photo file IDs and ratings.
* Does NOT send any Telegram notifications (no officer/citizen spam).

Usage
-----
    python migrate_sheets_to_db.py --dry-run     # report only
    python migrate_sheets_to_db.py               # write
"""
import argparse
import logging
from datetime import datetime

from core import escalation, service
from core.db import SessionLocal, init_db
from core.models import (CitizenFeedback, Complaint, ComplaintHistory,
                         ComplaintImage, Officer)
from core.seed import ensure_seed

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("migrate")


def _parse_ts(value):
    if not value:
        return datetime.utcnow()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S", "%m/%d/%Y %H:%M:%S"):
        try:
            return datetime.strptime(str(value).strip(), fmt)
        except ValueError:
            continue
    return datetime.utcnow()


def _int_or_none(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _float_or_none(value):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def migrate_officers(db, dry_run: bool) -> dict:
    from sheets import SHEET_URL, get_client

    stats = {"created": 0, "skipped": 0}
    client = get_client()
    if not client:
        log.error("Google Sheets client unavailable - check GOOGLE_SHEETS_CREDENTIALS")
        return stats

    try:
        ws = client.open_by_url(SHEET_URL).worksheet("Officer Details")
    except Exception as exc:
        log.warning("No 'Officer Details' sheet (%s); skipping officers", exc)
        return stats

    pending_reports = []
    for row in ws.get_all_records():
        code = str(row.get("Officer_ID") or "").strip()
        name = str(row.get("Full_Name") or "").strip()
        if not name:
            continue
        if code and db.query(Officer.id).filter(Officer.employee_code == code).first():
            stats["skipped"] += 1
            continue

        sector = str(row.get("Sector") or "").strip()
        category = service.resolve_category(db, sector) if sector else None
        level_raw = str(row.get("Level") or "1").strip().upper()
        level = {"L1": 1, "FIELD": 1, "L2": 2, "L3": 3, "L4": 4}.get(
            level_raw, _int_or_none(level_raw) or 1)

        officer = Officer(
            employee_code=code, full_name=name,
            designation=str(row.get("Designation") or ""),
            department_id=category.department_id if category else None,
            level=max(1, min(4, level)),
            mobile=str(row.get("Mobile") or ""),
            telegram_chat_id=str(row.get("Telegram_Chat_ID") or "").strip() or None,
            jurisdiction_type="block",
            jurisdiction_value=str(row.get("Zone") or ""),
            active=True,
        )
        if not dry_run:
            db.add(officer)
            db.flush()
        stats["created"] += 1
        if code and str(row.get("Reports_To") or "").strip():
            pending_reports.append((officer, str(row.get("Reports_To")).strip()))

    if not dry_run:
        db.flush()
        for officer, reports_to in pending_reports:
            boss = db.query(Officer).filter(Officer.employee_code == reports_to).one_or_none()
            if boss and boss.id != officer.id:
                officer.reports_to_id = boss.id
        db.commit()
    return stats


def migrate_tickets(db, dry_run: bool, grace: bool = True) -> dict:
    from sheets import SHEET_URL, get_client

    stats = {"created": 0, "skipped": 0, "needs_review": 0}
    client = get_client()
    if not client:
        log.error("Google Sheets client unavailable - check GOOGLE_SHEETS_CREDENTIALS")
        return stats

    for row in client.open_by_url(SHEET_URL).sheet1.get_all_records():
        ref = str(row.get("Ticket ID") or "").strip()
        if not ref:
            continue
        if db.query(Complaint.id).filter(Complaint.ticket_ref == ref).first():
            stats["skipped"] += 1
            continue

        created = _parse_ts(row.get("Timestamp"))
        category = service.resolve_category(db, str(row.get("Category") or ""))
        status_raw = str(row.get("Status") or "Open").strip().lower()
        status = "RESOLVED" if status_raw.startswith("resolv") else "ASSIGNED"

        officer_name = str(row.get("Officer") or "").strip()
        officer = None
        if officer_name:
            officer = (db.query(Officer)
                       .filter(Officer.full_name == officer_name,
                               Officer.department_id == (category.department_id if category else None))
                       .first())

        complaint = Complaint(
            ticket_ref=ref,
            citizen_chat_id=str(row.get("Chat ID") or "legacy"),
            department_id=category.department_id if category else None,
            category_id=category.id if category else None,
            severity=str(row.get("Severity") or "Medium").title(),
            description=str(row.get("Description") or ""),
            lat=_float_or_none(row.get("Lat")),
            lon=_float_or_none(row.get("Long")),
            pincode=str(row.get("Pin Code") or ""),
            area=str(row.get("Area") or ""),
            map_link=str(row.get("Map Link") or ""),
            status=status,
            level=officer.level if officer else 1,
            assigned_officer_id=officer.id if officer else None,
            created_at=created,
            resolved_at=created if status == "RESOLVED" else None,
            integrity_metric=str(row.get("Integrity Metric") or "Validated"),
        )

        if status != "RESOLVED" and category:
            rule = escalation.get_rule(db, category.department_id, category.id)
            if officer:
                base = datetime.utcnow() if grace else created
                complaint.escalation_due_at = escalation.deadline_for(
                    rule, complaint.level, base)

        if category is None:
            complaint.status = "NEEDS_REVIEW"
            stats["needs_review"] += 1

        if not dry_run:
            db.add(complaint)
            db.flush()
            if str(row.get("PhotoID") or "").strip():
                db.add(ComplaintImage(complaint_id=complaint.id, kind="original",
                                      telegram_file_id=str(row.get("PhotoID")).strip()))
            if str(row.get("After File ID") or "").strip():
                db.add(ComplaintImage(complaint_id=complaint.id, kind="resolution",
                                      telegram_file_id=str(row.get("After File ID")).strip()))
            rating = _int_or_none(row.get("User Rating"))
            if rating:
                db.add(CitizenFeedback(complaint_id=complaint.id, rating=rating,
                                       resolution_confirmed=True))
            db.add(ComplaintHistory(complaint_id=complaint.id, action="migrated",
                                    actor_type="system", actor_id="sheets-migration",
                                    note="Imported from Google Sheet"))
        stats["created"] += 1

    if not dry_run:
        db.commit()
    return stats


def main():
    parser = argparse.ArgumentParser(description="Migrate Google Sheets into the platform DB")
    parser.add_argument("--dry-run", action="store_true", help="report only, write nothing")
    parser.add_argument("--no-grace", action="store_true",
                        help="start TAT from the original timestamp instead of now")
    args = parser.parse_args()

    log.info("Database: %s", init_db())
    db = SessionLocal()
    try:
        ensure_seed(db)
        officers = migrate_officers(db, args.dry_run)
        tickets = migrate_tickets(db, args.dry_run, grace=not args.no_grace)
        log.info("Officers: %s", officers)
        log.info("Tickets:  %s", tickets)
        log.info("DRY RUN - nothing written" if args.dry_run
                 else "Migration complete: existing rows skipped, nothing deleted.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

