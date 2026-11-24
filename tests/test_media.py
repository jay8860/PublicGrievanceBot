"""Photos are archived on the media volume, not only kept as Telegram file_ids."""
from fastapi.testclient import TestClient

import api
from core import media, service
from core.models import ComplaintImage
from core.security import create_token
from core.seed import ensure_seed

BEFORE = b"\xff\xd8before-bytes"
AFTER = b"\xff\xd8after-bytes"


def _headers():
    return {"Authorization": f"Bearer {create_token('admin', role='superadmin')}"}


def _complaint(db):
    ensure_seed(db)
    return service.create_complaint(
        db, citizen_chat_id="900001", description="Pothole outside the school",
        category_label="Potholes", severity="High", lat=20.707, lon=81.55,
        photo_file_id="tg-file-1", photo_bytes=BEFORE)


def test_save_photo_writes_under_media_root(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))

    key = media.save_photo(BEFORE, "GRV-2026-000001", "original")

    assert key.startswith("photos/") and key.endswith(".jpg")
    path = media.photo_path(key)
    assert path is not None
    with open(path, "rb") as handle:
        assert handle.read() == BEFORE
    assert media.usage_bytes() == len(BEFORE)


def test_archiving_is_optional(monkeypatch):
    monkeypatch.delenv("MEDIA_ROOT", raising=False)

    assert media.enabled() is False
    assert media.save_photo(BEFORE, "GRV-2026-000002") == ""
    assert media.photo_path("photos/2026/x.jpg") is None


def test_photo_path_refuses_to_escape_the_root(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))

    assert media.photo_path("../grievance.db") is None
    assert media.photo_path("photos/../../etc/passwd") is None


def test_ticket_name_cannot_break_out_of_the_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))

    key = media.save_photo(BEFORE, "../../GRV/../../evil", "original")

    assert ".." not in key
    assert media.photo_path(key) is not None


def test_create_complaint_archives_the_citizen_photo(db, tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))

    complaint = _complaint(db)
    row = (db.query(ComplaintImage)
           .filter(ComplaintImage.complaint_id == complaint.id,
                   ComplaintImage.kind == "original")
           .one())

    assert row.telegram_file_id == "tg-file-1"
    assert row.storage_key.startswith("photos/")
    with open(media.photo_path(row.storage_key), "rb") as handle:
        assert handle.read() == BEFORE


def test_resolution_photo_is_archived_too(db, tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))

    complaint = _complaint(db)
    service.resolve(db, complaint, after_bytes=AFTER, notes="road repaired",
                    actor_type="admin", actor_id="tester")

    row = (db.query(ComplaintImage)
           .filter(ComplaintImage.complaint_id == complaint.id,
                   ComplaintImage.kind == "resolution")
           .one())
    assert row.storage_key.startswith("photos/")
    with open(media.photo_path(row.storage_key), "rb") as handle:
        assert handle.read() == AFTER


def test_api_serves_the_archived_photo(db, tmp_path, monkeypatch):
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path))
    complaint = _complaint(db)

    with TestClient(api.app) as client:
        detail = client.get(f"/api/v2/complaints/{complaint.id}",
                            headers=_headers()).json()
        photo = next(item for item in detail["images"] if item["kind"] == "original")
        assert photo["stored"] is True
        assert photo["url"] == f"/v2/complaints/{complaint.id}/images/original"

        url = f"/api/v2/complaints/{complaint.id}/images/original"
        assert client.get(url).status_code == 401

        response = client.get(url, headers=_headers())
        assert response.status_code == 200
        assert response.content == BEFORE

        bad = client.get(f"/api/v2/complaints/{complaint.id}/images/thumbnail",
                         headers=_headers())
        assert bad.status_code == 400


def test_missing_archive_is_reported_not_guessed(db, monkeypatch):
    monkeypatch.delenv("MEDIA_ROOT", raising=False)
    complaint = _complaint(db)                     # nothing written to disk

    with TestClient(api.app) as client:
        detail = client.get(f"/api/v2/complaints/{complaint.id}",
                            headers=_headers()).json()
        photo = next(item for item in detail["images"] if item["kind"] == "original")
        assert photo["stored"] is False
        assert photo["url"] == ""

        response = client.get(f"/api/v2/complaints/{complaint.id}/images/original",
                              headers=_headers())
        assert response.status_code == 404
