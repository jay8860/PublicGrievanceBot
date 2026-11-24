"""Officer onboarding: single-use, expiring, uniquely-mapped invitation codes."""
from datetime import datetime, timedelta

from core import service
from core.models import InvitationCode, Officer, TelegramMapping
from core.seed import ensure_seed


def _officer(db, name="Sanitation Officer"):
    depts = ensure_seed(db)
    officer = Officer(full_name=name, department_id=depts["MUNICIPAL"].id, level=1,
                      jurisdiction_type="district", active=True)
    db.add(officer)
    db.commit()
    return officer


def test_code_links_telegram_account_once(db):
    officer = _officer(db)
    invitation = service.create_invitation(db, officer, "admin", ttl_hours=24)
    assert invitation.code.startswith("GRV-")

    linked, error = service.redeem_invitation(db, invitation.code, "123456789")
    assert error == ""
    assert linked.id == officer.id
    db.refresh(officer)
    assert officer.telegram_chat_id == "123456789"
    assert db.query(TelegramMapping).filter_by(officer_id=officer.id).count() == 1

    # Same code cannot be reused.
    again, error = service.redeem_invitation(db, invitation.code, "987654321")
    assert again is None
    assert "already been used" in error


def test_expired_and_unknown_codes_are_rejected(db):
    officer = _officer(db)
    invitation = service.create_invitation(db, officer, "admin", ttl_hours=1)
    invitation.expires_at = datetime.utcnow() - timedelta(minutes=1)
    db.commit()

    linked, error = service.redeem_invitation(db, invitation.code, "555")
    assert linked is None and "expired" in error

    linked, error = service.redeem_invitation(db, "GRV-DOESNOTEXIST", "555")
    assert linked is None and "does not exist" in error


def test_one_telegram_account_cannot_be_mapped_to_two_officers(db):
    first = _officer(db, "Officer One")
    second = _officer(db, "Officer Two")
    code_one = service.create_invitation(db, first, "admin")
    code_two = service.create_invitation(db, second, "admin")

    linked, error = service.redeem_invitation(db, code_one.code, "777")
    assert error == "" and linked.id == first.id

    linked, error = service.redeem_invitation(db, code_two.code, "777")
    assert linked is None
    assert "already linked" in error


def test_revocation_clears_the_link_and_closes_the_mapping(db):
    officer = _officer(db)
    code = service.create_invitation(db, officer, "admin")
    service.redeem_invitation(db, code.code, "888")

    service.revoke_telegram_access(db, officer, "left the department", "admin")
    db.refresh(officer)
    assert officer.telegram_chat_id is None
    assert officer.telegram_revoked_at is not None
    mapping = db.query(TelegramMapping).filter_by(officer_id=officer.id).one()
    assert mapping.unlinked_at is not None


def test_new_code_revokes_previous_outstanding_codes(db):
    officer = _officer(db)
    first = service.create_invitation(db, officer, "admin")
    second = service.create_invitation(db, officer, "admin")

    service.redeem_invitation(db, second.code, "999")
    db.refresh(first)
    assert first.revoked_at is not None


def test_officer_action_scope(db):
    """RBAC helper: same department + level, otherwise denied."""
    depts = ensure_seed(db)
    pwd_l1 = Officer(full_name="PWD L1", department_id=depts["PWD"].id, level=1, active=True)
    pwd_l3 = Officer(full_name="PWD L3", department_id=depts["PWD"].id, level=3, active=True)
    phe_l3 = Officer(full_name="PHE L3", department_id=depts["PHE"].id, level=3, active=True)
    db.add_all([pwd_l1, pwd_l3, phe_l3])
    db.commit()

    complaint = service.create_complaint(db, citizen_chat_id="c", description="Pothole",
                                         category_label="Road Infra")
    assert service.officer_may_act(db, complaint, pwd_l1) is True
    assert service.officer_may_act(db, complaint, pwd_l3) is True
    assert service.officer_may_act(db, complaint, phe_l3) is False   # wrong department
