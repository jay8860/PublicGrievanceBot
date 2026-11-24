"""Geographical routing + duplicate grouping.

Routing order (most specific first):
    village -> ward -> block -> district-wide officer
Officers can hold several jurisdictions via ``OfficerJurisdiction``; when more
than one L1 matches, the least-loaded available officer wins (workload
distribution) instead of "last row in the sheet wins".
"""
import logging
from datetime import datetime, timedelta
from math import asin, cos, radians, sin, sqrt
from typing import Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from .models import (Complaint, Officer, OfficerJurisdiction)

logger = logging.getLogger(__name__)

OPEN_STATUSES = ("NEW", "ASSIGNED", "ACKNOWLEDGED", "IN_PROGRESS", "ESCALATED", "REOPENED")
DUPLICATE_RADIUS_M = 500.0
DUPLICATE_WINDOW_HOURS = 72


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres."""
    if None in (lat1, lon1, lat2, lon2):
        return float("inf")
    r = 6371000.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def _jurisdiction_sets(db: Session, officer_ids: Iterable[str]) -> dict:
    rows = db.query(OfficerJurisdiction).filter(OfficerJurisdiction.officer_id.in_(list(officer_ids))).all()
    scopes: dict[str, dict] = {}
    for row in rows:
        scopes.setdefault(row.officer_id, {}).setdefault(row.scope_type, set()).add(
            (row.scope_value or "").strip().lower())
    return scopes


def _specificity(officer: Officer, scopes: dict, ctx: dict) -> int:
    """3 = village, 2 = ward, 1 = block, 0 = district fallback."""
    mine = scopes.get(officer.id, {})
    if ctx["village"] and ctx["village"] in mine.get("village", set()):
        return 3
    if ctx["ward"] and ctx["ward"] in mine.get("ward", set()):
        return 2
    if ctx["block"] and ctx["block"] in mine.get("block", set()):
        return 1
    if officer.jurisdiction_type == "district":
        return 0
    value = (officer.jurisdiction_value or "").strip().lower()
    if value and value in (ctx["village"], ctx["ward"], ctx["block"], ctx["area"]):
        return 1
    return -1


def find_officer(db: Session, *, department_id: Optional[str], level: int = 1,
                 ward: str = "", village: str = "", block: str = "", area: str = "",
                 lat: Optional[float] = None, lon: Optional[float] = None) -> Optional[Officer]:
    """Pick the responsible officer for a department/level/area."""
    if not department_id:
        return None

    candidates = (db.query(Officer)
                  .filter(Officer.department_id == department_id,
                          Officer.level == level,
                          Officer.active.is_(True),
                          Officer.available.is_(True))
                  .all())
    if not candidates:
        return None

    ctx = {
        "ward": (ward or "").strip().lower(),
        "village": (village or "").strip().lower(),
        "block": (block or "").strip().lower(),
        "area": (area or "").strip().lower(),
    }
    scopes = _jurisdiction_sets(db, [o.id for o in candidates])

    scored = [(o, _specificity(o, scopes, ctx)) for o in candidates]
    matched = [(o, score) for o, score in scored if score >= 0]
    if not matched:
        return None          # -> caller flags the complaint for administrative review

    best_score = max(score for _, score in matched)
    shortlist = [o for o, score in matched if score == best_score]

    # Workload-aware tie-break: fewest open complaints wins.
    def open_load(officer: Officer) -> int:
        return (db.query(func.count(Complaint.id))
                .filter(Complaint.assigned_officer_id == officer.id,
                        Complaint.status.in_(OPEN_STATUSES))
                .scalar() or 0)

    shortlist.sort(key=lambda o: (open_load(o), o.full_name or ""))
    return shortlist[0]


def escalations_chain(db: Session, department_id: Optional[str], start_level: int) -> list[Officer]:
    """Officers at each level above ``start_level`` (used by the TAT engine)."""
    if not department_id:
        return []
    return (db.query(Officer)
            .filter(Officer.department_id == department_id,
                    Officer.level > start_level,
                    Officer.active.is_(True))
            .order_by(Officer.level.asc())
            .all())


def find_duplicate_group(db: Session, *, category_id: Optional[str], lat: Optional[float],
                         lon: Optional[float], exclude_id: Optional[str] = None) -> Optional[str]:
    """Return an existing group_id for a nearby, recent, same-category complaint.

    Submissions are **never discarded** - the new complaint is linked into the
    same group so the dashboard can show "N citizens reported this".
    """
    if not category_id or lat is None or lon is None:
        return None

    since = datetime.utcnow() - timedelta(hours=DUPLICATE_WINDOW_HOURS)
    query = (db.query(Complaint)
             .filter(Complaint.category_id == category_id,
                     Complaint.created_at >= since,
                     Complaint.lat.isnot(None),
                     Complaint.lon.isnot(None)))
    if exclude_id:
        query = query.filter(Complaint.id != exclude_id)

    for other in query.order_by(Complaint.created_at.desc()).limit(50).all():
        if haversine_m(lat, lon, other.lat, other.lon) <= DUPLICATE_RADIUS_M:
            return other.group_id or other.id
    return None
