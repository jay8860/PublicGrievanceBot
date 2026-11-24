"""Seed the five departments, their categories and default TAT rules.

Idempotent: safe to run on every start (``ensure_seed(db)``) - it only inserts
rows that do not exist yet and never deletes or overwrites admin edits.
"""
import logging

from sqlalchemy.orm import Session

from config import get_env

from .models import AdminUser, Category, Department, EscalationRule, Officer
from .security import hash_password

logger = logging.getLogger(__name__)

# code, display name, description
DEPARTMENTS = [
    ("MUNICIPAL", "Municipal Corporation",
     "Garbage, drainage, sanitation, street lighting and public cleanliness."),
    ("REVENUE", "Revenue Department",
     "Land records, mutation, certificates and other revenue grievances."),
    ("PWD", "Public Works Department (PWD)",
     "Potholes, damaged roads, road infrastructure and bridges."),
    ("PHE", "Public Health Engineering (PHE / Water Supply)",
     "Water shortages, pipeline leakage and contaminated water."),
    ("ELECTRICITY", "Electricity Department",
     "Power interruptions, transformers and street electrical infrastructure."),
]

# department code -> [(category name, ai label used by the vision model)]
CATEGORIES = {
    "MUNICIPAL": [
        ("Garbage Accumulation", "Sanitation"),
        ("Drainage", "Drainage"),
        ("Streetlights", "Lighting"),
        ("Public Cleanliness", "Cleanliness"),
        ("Fire Hazard", "Fire"),
        ("Other Municipal Issue", "Other"),
    ],
    "REVENUE": [
        ("Land Records", "Land Revenue"),
        ("Mutation Issues", "Mutation"),
        ("Certificates", "Certificates"),
        ("Other Revenue Grievance", "Revenue Other"),
    ],
    "PWD": [
        ("Potholes", "Road Infra"),
        ("Damaged Roads", "Road Damage"),
        ("Road Infrastructure", "Road Infrastructure"),
        ("Damaged Bridges", "Bridge Damage"),
    ],
    "PHE": [
        ("Water Shortage", "Water Shortage"),
        ("Pipeline Leakage", "Pipeline Leakage"),
        ("Contaminated Water", "Contaminated Water"),
        ("Public Water Supply", "Water Supply"),
    ],
    "ELECTRICITY": [
        ("Power Interruption", "Power Outage"),
        ("Damaged Transformer", "Transformer Damage"),
        ("Damaged Electrical Infrastructure", "Electrical Damage"),
        ("Street Electrical Issue", "Street Electricity"),
    ],
}


def ensure_departments(db: Session) -> dict:
    """Create the five departments + their categories; returns {code: Department}."""
    by_code = {}
    for code, name, description in DEPARTMENTS:
        dept = db.query(Department).filter(Department.code == code).one_or_none()
        if dept is None:
            dept = Department(code=code, name=name, description=description)
            db.add(dept)
            db.flush()
            logger.info("Seeded department %s", code)
        by_code[code] = dept

    for code, cats in CATEGORIES.items():
        dept = by_code[code]
        for cat_name, ai_label in cats:
            exists = (db.query(Category)
                      .filter(Category.department_id == dept.id, Category.name == cat_name)
                      .one_or_none())
            if exists is None:
                db.add(Category(department_id=dept.id, name=cat_name, ai_label=ai_label))
    db.flush()
    return by_code


def ensure_rules(db: Session) -> None:
    """Default TAT policy per department (admin-editable afterwards)."""
    for dept in db.query(Department).all():
        rule = (db.query(EscalationRule)
                .filter(EscalationRule.department_id == dept.id,
                        EscalationRule.category_id.is_(None))
                .one_or_none())
        if rule is None:
            db.add(EscalationRule(department_id=dept.id))
    db.flush()


def ensure_bootstrap_admin(db: Session, department_map: dict | None = None) -> None:
    """Create the first superadmin from ADMIN_USERNAME/ADMIN_PASSWORD.

    Never resets an existing account's password, so an admin who changes their
    password in the dashboard keeps it across redeploys.
    """
    username = get_env("ADMIN_USERNAME", "admin")
    password = get_env("ADMIN_PASSWORD", "admin123")

    user = db.query(AdminUser).filter(AdminUser.username == username).one_or_none()
    if user is None:
        db.add(AdminUser(username=username, password_hash=hash_password(password), role="superadmin"))
        db.flush()
        logger.info("Bootstrapped superadmin '%s' from environment", username)
        if password == "admin123":
            logger.warning(
                "SECURITY: ADMIN_PASSWORD is the insecure default 'admin123'. "
                "Change it (env var or dashboard) before a public rollout."
            )


def ensure_seed(db: Session) -> dict:
    """Run every idempotent seeding step and commit."""
    depts = ensure_departments(db)
    ensure_rules(db)
    ensure_bootstrap_admin(db, depts)
    db.commit()
    return depts


def officer_exists(db: Session) -> bool:
    return db.query(Officer).count() > 0
