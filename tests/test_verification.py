"""Resolution flow: AI auto-approves a clean fix; anything else waits for a human."""
import pytest

from core import service
from core.models import ComplaintHistory, ComplaintImage, Officer
from core.seed import ensure_seed


def _resolved_fixture(db):
    depts = ensure_seed(db)
    pwd = depts["PWD"]
    officer = Officer(full_name="PWD L1", department_id=pwd.id, level=1,
                      jurisdiction_type="district", active=True, available=True)
    db.add(officer)
    db.commit()

    complaint = service.create_complaint(db, citizen_chat_id="citizen-1",
                                         description="Deep pothole near the school",
                                         category_label="Road Infra")
    # create_complaint already inserts the original-image row; give it the
    # Telegram file id the verifier will download.
    original = (db.query(ComplaintImage)
                .filter(ComplaintImage.complaint_id == complaint.id,
                        ComplaintImage.kind == "original").first())
    original.telegram_file_id = "orig-file"
    db.commit()
    return complaint



def _fake_photos(monkeypatch):
    monkeypatch.setattr(service, "_telegram_photo_bytes",
                        lambda file_id: b"photo" if file_id else None)


def _fake_verdict(monkeypatch, **overrides):
    payload = {"verdict": "verified", "confidence": 0.91, "same_location": "yes",
               "evidence": "garbage cleared and road patched", "error": ""}
    payload.update(overrides)
    monkeypatch.setattr(service.verify, "verify_resolution",
                        lambda *args, **kwargs: dict(payload))
    return payload


def _history(db, complaint):
    return [row.action for row in
            db.query(ComplaintHistory).filter(ComplaintHistory.complaint_id == complaint.id).all()]


def test_verified_resolution_is_auto_approved(db, monkeypatch):
    complaint = _resolved_fixture(db)
    _fake_photos(monkeypatch)
    _fake_verdict(monkeypatch)

    result = service.resolve(db, complaint, after_bytes=b"after", after_file_id="after-file",
                             actor_type="officer", actor_id="officer-1")
    db.refresh(complaint)

    assert result["auto_approved"] is True
    assert complaint.status == "VERIFIED"
    assert complaint.resolution_verification == "verified"
    assert "verification_auto_approved" in _history(db, complaint)
    assert "verification_pending" not in _history(db, complaint)
    assert complaint.resolved_at is not None


def test_uncertain_verdict_goes_to_verification_queue(db, monkeypatch):
    complaint = _resolved_fixture(db)
    _fake_photos(monkeypatch)
    _fake_verdict(monkeypatch, verdict="requires_review", confidence=0.4,
                  same_location="unsure", evidence="angle differs")

    result = service.resolve(db, complaint, after_bytes=b"after", after_file_id="after-file")
    db.refresh(complaint)

    assert result["auto_approved"] is False
    assert complaint.status == "RESOLVED"          # waits for a human decision
    assert complaint.resolution_verification == "requires_review"
    assert "verification_pending" in _history(db, complaint)
    assert "verification_auto_approved" not in _history(db, complaint)


def test_ai_error_falls_back_to_manual_verification(db, monkeypatch):
    """No key / network / bad JSON: the complaint must NOT be auto-approved."""
    complaint = _resolved_fixture(db)
    _fake_photos(monkeypatch)
    _fake_verdict(monkeypatch, verdict="requires_review", confidence=0.0,
                  same_location="unsure", evidence="",
                  error="OPENROUTER_API_KEY is not set")

    result = service.resolve(db, complaint, after_bytes=b"after", after_file_id="after-file")
    db.refresh(complaint)

    assert result["auto_approved"] is False
    assert complaint.status == "RESOLVED"
    assert complaint.resolution_verification == "requires_review"
    assert "OPENROUTER_API_KEY" in result["pending_reason"]


def test_missing_photos_fall_back_to_manual_verification(db, monkeypatch):
    complaint = _resolved_fixture(db)
    monkeypatch.setattr(service, "_telegram_photo_bytes", lambda file_id: None)

    result = service.resolve(db, complaint, after_file_id="")
    db.refresh(complaint)

    assert result["auto_approved"] is False
    assert complaint.resolution_verification == "requires_review"
    assert "unavailable" in result["pending_reason"].lower()


def test_auto_approval_can_be_switched_off(db, monkeypatch):
    complaint = _resolved_fixture(db)
    _fake_photos(monkeypatch)
    _fake_verdict(monkeypatch)
    monkeypatch.setenv("AUTO_APPROVE_AI_RESOLUTION", "false")

    result = service.resolve(db, complaint, after_bytes=b"after", after_file_id="after-file")
    db.refresh(complaint)

    assert result["auto_approved"] is False
    assert complaint.status == "RESOLVED"
    assert complaint.resolution_verification == "verified"
    assert "verification_pending" in _history(db, complaint)


def test_citizen_confirmation_closes_auto_approved_complaint(db, monkeypatch):
    complaint = _resolved_fixture(db)
    _fake_photos(monkeypatch)
    _fake_verdict(monkeypatch)
    service.resolve(db, complaint, after_bytes=b"after", after_file_id="after-file")

    service.citizen_feedback(db, complaint, confirmed=True, rating=5)
    db.refresh(complaint)

    assert complaint.status == "CLOSED"
    assert complaint.closed_at is not None
