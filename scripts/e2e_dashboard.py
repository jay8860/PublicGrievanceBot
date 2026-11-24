"""End-to-end test of every action the dashboard triggers (local API, demo DB)."""
import json
import sys

import requests

BASE = "http://127.0.0.1:8010"
out = open("_e2e_report.txt", "w", encoding="utf-8")


def log(*args):
    out.write(" ".join(str(a) for a in args) + "\n")


def jget(path, **kw):
    r = requests.get(f"{BASE}{path}", headers=HEAD, timeout=60, **kw)
    return r.status_code, (r.json() if "json" in r.headers.get("content-type", "") else r)


def jpost(path, payload=None):
    r = requests.post(f"{BASE}{path}", headers=HEAD, json=payload or {}, timeout=60)
    body = r.json() if "json" in r.headers.get("content-type", "") else {}
    return r.status_code, body


login = requests.post(f"{BASE}/api/login",
                      json={"username": "admin", "password": "admin123"}, timeout=20)
TOKEN = login.json()["access_token"]
HEAD = {"Authorization": f"Bearer {TOKEN}"}
log("login:", login.status_code, "role:", login.json().get("role"))

code, me = jget("/api/v2/me")
log("me:", code, me.get("username"), me.get("role"))

code, depts = jget("/api/v2/departments")
log("departments:", code, [d["code"] for d in depts])
municipal = next(d for d in depts if d["code"] == "MUNICIPAL")

code, cats = jget(f"/api/v2/departments/{municipal['id']}/categories")
log("categories:", code, len(cats), "first:", cats[0]["name"] if cats else None)

# 1. Officer creation (Add officer form)
code, officer = jpost("/api/v2/officers", {
    "full_name": "E2E Test Officer", "designation": "Sanitation Inspector",
    "department_id": municipal["id"], "level": 1, "employee_code": "E2E-L1",
    "mobile": "9000000001", "email": "e2e@dhamtari.gov.in",
    "jurisdiction_type": "ward", "jurisdiction_value": "Ward 9",
    "jurisdictions": [{"scope_type": "ward", "scope_value": "Ward 9"}],
})
log("create officer:", code, officer.get("full_name"), "id:", officer.get("id", "")[:8])

# 2. Telegram onboarding (Invitation modal)
code, invite = jpost(f"/api/v2/officers/{officer['id']}/invitation", {"ttl_hours": 24})
log("invitation:", code, "code:", invite.get("code"), "expires:", invite.get("expires_at"))
code, codes = jget(f"/api/v2/officers/{officer['id']}/codes")
log("invitation history:", code, len(codes))

# 3. Complaint management actions
code, listing = jget("/api/v2/complaints?status=NEEDS_REVIEW&limit=5")
items = listing.get("items", [])
log("needs-review queue:", code, "total:", listing.get("total"))
target = items[0] if items else None

if target:
    # Assign an officer from the complaint's own department (server rejects a
    # cross-department assignment) - reuse an existing L1 or create one.
    code, same_dept_officers = jget(f"/api/v2/officers?department_id={target['department_id']}")
    l1 = next((o for o in same_dept_officers if o["level"] == 1 and o["active"]), None)
    if l1 is None:
        code, l1 = jpost("/api/v2/officers", {
            "full_name": f"E2E {target['department']} L1", "level": 1,
            "department_id": target["department_id"], "jurisdiction_type": "district",
        })
    code, assigned = jpost(f"/api/v2/complaints/{target['id']}/assign",
                           {"officer_id": l1["id"], "reason": "e2e assignment"})
    log("assign:", code, assigned.get("status"), "officer:", assigned.get("assigned_officer"))

    code, acked = jpost(f"/api/v2/complaints/{target['id']}/acknowledge")
    log("acknowledge:", code, acked.get("status"))
    code, prog = jpost(f"/api/v2/complaints/{target['id']}/progress", {"note": "e2e work started"})
    log("in progress:", code, prog.get("status"))
    code, esc = jpost(f"/api/v2/complaints/{target['id']}/escalate", {"note": "e2e escalation"})
    log("escalate:", code, "level:", esc.get("level"), "status:", esc.get("status"))
else:
    log("needs-review queue: EMPTY (skipped assign/ack/progress/escalate)")

# 4. Resolution + verification decision
code, resolved_list = jget("/api/v2/complaints?status=RESOLVED&limit=5")
resolved = (resolved_list.get("items") or [None])[0]
if resolved:
    code, verifs = jget("/api/v2/verifications?verdict=requires_review")
    log("verification queue:", code, len(verifs))
    code, decision = jpost(f"/api/v2/complaints/{resolved['id']}/verification",
                           {"action": "approve", "note": "e2e approved"})
    log("verification approve:", code, decision.get("status"),
        decision.get("resolution_verification"))

# 5. Analytics used by the pages
for path in ["/api/v2/analytics/dashboard", "/api/v2/analytics/officer-performance",
             "/api/v2/analytics/wards", "/api/v2/analytics/trends?months=6",
             "/api/v2/escalation-centre", "/api/v2/analytics/geo"]:
    code, data = jget(path)
    size = len(data) if isinstance(data, list) else len(data.keys())
    log(f"analytics {path}:", code, "size:", size)

# 6. Reports (CSV + Excel)
for fmt in ("csv", "xlsx"):
    r = requests.get(f"{BASE}/api/v2/reports/complaints", headers=HEAD,
                     params={"format": fmt}, timeout=60)
    log(f"report {fmt}:", r.status_code, r.headers.get("content-type", "")[:45],
        "bytes:", len(r.content))

# 7. Audit trail now has entries
code, logs = jget("/api/v2/audit-logs?limit=200")
log("audit logs:", code, len(logs), "latest:", logs[0]["action"] if logs else None)

# 8. Security panel
code, status = jget("/api/v2/security-status")
log("security-status:", code, "db:", status.get("database"),
    "scheduler:", status.get("scheduler_enabled"))

# 9. Password change validation (wrong current password must be rejected)
r = requests.post(f"{BASE}/api/v2/admins/me/password", headers=HEAD,
                  json={"current_password": "wrong-password", "new_password": "AnotherPass123"},
                  timeout=20)
log("password change (wrong current):", r.status_code, r.json().get("detail"))

out.close()
print("E2E DONE")
