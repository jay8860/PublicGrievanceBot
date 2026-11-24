"""API tests for the /api/v2 surface (auth, departments, officers, reports)."""
from fastapi.testclient import TestClient

from core.db import SessionLocal
from core.security import create_token
from core.seed import ensure_seed

import api


def _admin_headers(role="superadmin"):
    return {"Authorization": f"Bearer {create_token('admin', role=role)}"}


def _client():
    return TestClient(api.app)


def test_v2_requires_authentication(db):
    ensure_seed(db)
    with _client() as client:
        assert client.get("/api/v2/departments").status_code == 401
        assert client.get("/api/v2/complaints").status_code == 401


def test_five_departments_are_seeded_and_listed(db):
    ensure_seed(db)
    with _client() as client:
        resp = client.get("/api/v2/departments", headers=_admin_headers())
        assert resp.status_code == 200
        codes = {d["code"] for d in resp.json()}
        assert codes == {"MUNICIPAL", "REVENUE", "PWD", "PHE", "ELECTRICITY"}


def test_officer_crud_and_invitation(db):
    ensure_seed(db)
    with _client() as client:
        headers = _admin_headers()
        depts = client.get("/api/v2/departments", headers=headers).json()
        pwd_id = next(d["id"] for d in depts if d["code"] == "PWD")

        created = client.post("/api/v2/officers", headers=headers, json={
            "full_name": "Rakesh Verma", "designation": "Junior Engineer",
            "department_id": pwd_id, "level": 1,
            "mobile": "9999999999", "jurisdiction_type": "ward",
            "jurisdiction_value": "Ward 5",
            "jurisdictions": [{"scope_type": "ward", "scope_value": "Ward 5"}],
        })
        assert created.status_code == 201
        officer = created.json()
        assert officer["level"] == 1
        assert officer["jurisdictions"][0]["scope_value"] == "Ward 5"

        invitation = client.post(f"/api/v2/officers/{officer['id']}/invitation",
                                 headers=headers, json={"ttl_hours": 24})
        assert invitation.status_code == 201
        assert invitation.json()["code"].startswith("GRV-")

        patched = client.patch(f"/api/v2/officers/{officer['id']}", headers=headers,
                               json={"level": 2, "available": False})
        assert patched.status_code == 200
        assert patched.json()["level"] == 2
        assert patched.json()["available"] is False


def test_escalation_rule_upsert_and_escalation_centre(db):
    depts = ensure_seed(db)
    pwd_id = depts["PWD"].id
    with _client() as client:
        headers = _admin_headers()
        rule = client.put(f"/api/v2/escalation-rules/{pwd_id}", headers=headers,
                          json={"ack_hours": 6, "action_hours": 12, "l1_hours": 36,
                                "l2_hours": 12, "l3_hours": 12, "l4_hours": 24,
                                "reminder_hours": 4, "working_days": [0, 1, 2, 3, 4, 5],
                                "holidays": []})
        assert rule.status_code == 200
        assert rule.json()["l1_hours"] == 36

        centre = client.get("/api/v2/escalation-centre", headers=headers)
        assert centre.status_code == 200
        assert "counts" in centre.json()

        overview = client.get("/api/v2/analytics/overview", headers=headers)
        assert overview.status_code == 200
        assert len(overview.json()["departments"]) == 5


def test_report_export_csv_and_xlsx(db):
    ensure_seed(db)
    with _client() as client:
        headers = _admin_headers()
        csv_resp = client.get("/api/v2/reports/complaints?format=csv", headers=headers)
        assert csv_resp.status_code == 200
        assert "text/csv" in csv_resp.headers["content-type"]
        assert b"Ticket" in csv_resp.content

        xlsx_resp = client.get("/api/v2/reports/complaints?format=xlsx", headers=headers)
        assert xlsx_resp.status_code == 200
        assert xlsx_resp.content[:2] == b"PK"        # xlsx is a zip archive


def test_role_based_access_control(db):
    ensure_seed(db)
    with _client() as client:
        viewer = _admin_headers(role="viewer")
        assert client.get("/api/v2/departments", headers=viewer).status_code == 200
        assert client.post("/api/v2/officers", headers=viewer, json={
            "full_name": "Nope", "level": 1}).status_code == 403

        # Only superadmin may create admin accounts.
        assert client.get("/api/v2/admins", headers=viewer).status_code == 403
        assert client.get("/api/v2/admins", headers=_admin_headers()).status_code == 200


def test_me_endpoint_reports_identity(db):
    ensure_seed(db)
    with _client() as client:
        me = client.get("/api/v2/me", headers=_admin_headers())
        assert me.status_code == 200
        assert me.json()["username"] == "admin"
        assert me.json()["role"] == "superadmin"
        assert me.json()["is_admin"] is True
