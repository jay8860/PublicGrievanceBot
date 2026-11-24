# District Grievance Platform — v2 upgrade report

This document describes the **implemented** upgrade of `PublicGrievanceBot` into a
District-Level Grievance Management + Automatic Escalation platform. It is
deliberately precise about what is done and what is not.

The existing citizen bot, the Google-Sheets flow and the current React dashboard
keep working unchanged; everything below is **additive**.

---

## 1. Features implemented in this increment

| Area | What works now |
|---|---|
| **Departments** | 5 seeded departments (Municipal, Revenue, PWD, PHE, Electricity) with configurable categories + AI labels. Seeded idempotently on startup; editable via API. |
| **Officer management** | L1–L4 logical levels, department, designation, mobile/email, multiple jurisdictions (district/block/ward/village), reporting officer, availability, activation, Telegram connection status, workload counters. |
| **Secure Telegram onboarding** | Admin generates a single-use, expiring invitation code (`GRV-XXXXXXXX`); the officer sends it to the bot (`/officer <code>` or as a plain message). Codes expire, are single-use, one Telegram account maps to exactly one officer, other outstanding codes are revoked, access can be revoked by an admin (audited in `telegram_mappings`). |
| **Geographical routing** | village → ward → block → district specificity, then least-loaded officer (workload balancing). No match → `NEEDS_REVIEW`, never a random assignment. |
| **Automatic complaint IDs** | `GRV-<year>-<sequence>` (UUID primary key + human reference). |
| **TAT engine** | Per-department TAT policy (ack / first action / L1 / L2 / L3 / L4 hours, reminder window, working days, holidays). Deadlines are persisted in the DB, so they survive restarts. |
| **Automatic escalation L1→L2→L3→L4** | Background scheduler inside the API **and** a standalone `worker.py`. Escalations are deduplicated with a unique `dedupe_key` (two workers cannot double-escalate). L4 expiry alerts only — a complaint is **never** auto-resolved or auto-closed. Every hop writes `escalation_history` + `complaint_history` + `audit_logs` and notifies the new officer (Telegram, with action buttons) and the citizen. |
| **Telegram officer actions** | Inline buttons Accept / In Progress / Submit Resolution / View Details / Escalate, all validated server-side against the officer's department + level. The bot is only transport — the database is the source of truth. |
| **Complaint lifecycle** | NEW → ASSIGNED → ACKNOWLEDGED → IN_PROGRESS → (ESCALATED) → RESOLVED → citizen confirm → CLOSED; `REOPENED` keeps full history; `NEEDS_REVIEW` for unclassified/unroutable complaints. |
| **SLA pause/resume** | Documented reason + actor stored; on resume the deadline shifts by the paused duration. |
| **Before/after AI verification** | On resolution the backend fetches the original Telegram photo + the after photo, asks OpenRouter for `{same_location, issue_addressed, confidence, verdict}`, applies guard rails (verified only if same location **and** confidence ≥ 0.7) and stores `verified` / `requires_review` / `failed`. It never auto-approves; failures degrade to manual review. |
| **Citizen feedback / reopening** | Confirm (→ CLOSED) or "still broken" (→ REOPENED, TAT restarts at L1, full history preserved). |
| **Duplicate grouping** | Same category + ≤ 500 m + ≤ 72 h → linked into one `group_id`. Every citizen submission is preserved (nothing discarded). |
| **Audit logging** | Every privileged mutation writes `audit_logs` (actor, action, entity, detail). |
| **Admin accounts (RBAC)** | Individual admin users (`superadmin` / `admin` / `viewer`) with bcrypt hashes; the legacy env admin still works and is bootstrapped as a `superadmin`. Role checks on every v2 endpoint. |
| **Reports** | CSV and Excel (`.xlsx`) export with department + date-range filters. |
| **Analytics APIs** | Overview KPIs (total/new/pending/resolved/overdue/escalated/avg resolution time/department table), officer performance, geo points for the map, escalation-centre buckets. |
| **Migration** | `migrate_sheets_to_db.py` imports officers + tickets (IDs, chat IDs, photo file IDs, ratings) idempotently, without deleting anything and without sending notifications. |

### Deliberately NOT done yet (do not assume these exist)

1. **React screens for the new modules** (Departments / Officers / Escalation Centre /
   Reports). All endpoints are live and tested, but the dashboard UI still shows the
   original map/list view — no dead buttons were added; the new screens simply are
   not built yet.
2. **PostgreSQL is supported but not provisioned.** Without `DATABASE_URL` the app
   uses a SQLite file inside the container, which is **wiped on every deploy**.
3. **Object storage (S3/GCS)** — photos are still referenced by Telegram `file_id`;
   AI verification downloads them on demand.
4. **Redis/BullMQ** — scheduling uses APScheduler in-process + `worker.py`
   (safe on one node because escalations are deduplicated in the DB).
5. **Hindi/Chhattisgarhi bot copy**, multi-photo complaints, ward-boundary polygons,
   perceptual-hash image dedupe.
6. **Officer dashboard login** (JWT with `role=officer`) — RBAC primitives exist, but
   officers currently act through Telegram only.


---

## 2. Files added / modified

**Added**

```
core/__init__.py   core/db.py        core/models.py    core/security.py
core/seed.py       core/audit.py     core/geo.py       core/notify.py
core/escalation.py core/service.py   core/ai.py        core/verify.py
core/bot_hooks.py
routers/__init__.py  routers/admin.py
worker.py            migrate_sheets_to_db.py   DB_UPGRADE.md
tests/conftest.py    tests/test_escalation.py  tests/test_routing.py
tests/test_onboarding.py  tests/test_api_v2.py  requirements-dev.txt
```

**Modified**

- `api.py` — lifespan (create tables + seed + start scheduler), `include_router(/api/v2)`,
  `/api/login` now checks DB admin accounts first, then the legacy env admin.
- `bot.py` — mirrors complaints into the DB, skips the duplicate legacy officer
  notification when the platform already assigned one, mirrors officer resolutions,
  registers the platform handlers (onboarding + buttons).
- `requirements.txt` — `sqlalchemy`, `psycopg2-binary`, `apscheduler`.
- `.gitignore`, `.env.example`, `README.md`.

---

## 3. Database changes

New tables (SQLAlchemy, `create_all`, non-destructive):
`departments`, `complaint_categories`, `officers`, `officer_jurisdictions`,
`telegram_mappings`, `invitation_codes`, `admin_users`, `escalation_rules`,
`complaints`, `complaint_images`, `complaint_history`, `escalation_history`,
`notifications`, `citizen_feedback`, `audit_logs`.

Key indexes: `(status, escalation_due_at)`, `(department_id, status)`,
`assigned_officer_id`, `created_at`, `(scope_type, scope_value)`,
`telegram_chat_id` (unique), `ticket_ref` (unique), `dedupe_key` (unique) on
escalations and notifications.

Google Sheets is untouched — nothing is deleted or rewritten there.

---

## 4. New environment variables

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./grievance.db` | **Set this to PostgreSQL in production.** `postgres://` URLs are normalised automatically. |
| `ESCALATION_TICK_SECONDS` | `300` | How often the TAT engine runs. |
| `ENABLE_ESCALATION_SCHEDULER` | `true` | Set `false` when running `worker.py` separately (harmless either way — escalations are deduplicated). |
| `PLATFORM_DB_ENABLED` | `true` | Bot mirrors complaints into the DB. `false` keeps the bot Sheets-only. |
| `TICKET_PREFIX` | `GRV` | Human ticket prefix (`GRV-2026-000001`). |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Dashboard/officer JWT lifetime. |
| `OPENROUTER_TIMEOUT_SECONDS` | `60` | Backend AI timeout (verification). |

Existing variables are unchanged (`TELEGRAM_BOT_TOKEN`, `OPENROUTER_API_KEY`,
`OPENROUTER_MODEL`, `GOOGLE_SHEETS_CREDENTIALS`, `ADMIN_USERNAME`,
`ADMIN_PASSWORD`, `SECRET_KEY`, `CORS_ORIGINS`, …).

---

## 5. API changes

All legacy endpoints are unchanged. New, under `/api/v2` (Bearer JWT):

| Method & path | Role | Purpose |
|---|---|---|
| `GET /me` | any auth | Identity/claims of the caller |
| `GET/POST /departments`, `PATCH /departments/{id}` | admin / superadmin | Department config |
| `GET /departments/{id}/categories`, `POST/PATCH /categories[/{id}]` | admin | Category + AI label config |
| `GET /escalation-rules`, `PUT /escalation-rules/{department_id}` | admin | TAT policy |
| `GET/POST /officers`, `GET/PATCH /officers/{id}` | admin | Officer CRUD (L1–L4, jurisdictions) |
| `POST /officers/{id}/invitation` | admin | One-time Telegram linking code |
| `POST /officers/{id}/revoke-telegram` | admin | Revoke Telegram access |
| `GET /officers/{id}/codes` | admin | Invitation history |
| `GET /complaints` (status, department, category, level, officer, overdue, search, paging) | admin | Complaint list |
| `GET /complaints/{id}` | admin | Detail + images + history + escalations + feedback |
| `POST /complaints/{id}/assign` | admin | Manual assign/reassign |
| `POST /complaints/{id}/acknowledge` · `/progress` · `/escalate` · `/pause` · `/resume` · `/resolve` · `/reopen` · `/feedback` | admin | Lifecycle actions (all audited) |
| `GET /escalation-centre` | admin | L1/L2/L3/L4 buckets + overdue/unacknowledged/reopened/needs-review |
| `GET /analytics/overview` · `/analytics/officers` · `/analytics/geo` | admin (geo: any auth) | KPIs, officer performance, map points |
| `GET /reports/complaints?format=csv\|xlsx` | admin | Export |
| `GET /audit-logs` | admin | Audit trail |
| `GET/POST /admins`, `POST /admins/{id}/deactivate` | superadmin | Individual admin accounts |

`POST /api/login` now returns `{access_token, token_type, role}` and accepts both
individual admin accounts and the legacy `ADMIN_USERNAME`/`ADMIN_PASSWORD`.

---

## 6. Tests performed

`python -m pytest tests -q` → **23 passed**.

- **Escalation** (`tests/test_escalation.py`): L1 assignment + deadline; L1→L2→L3→L4
  progression; duplicate-tick protection (unique dedupe key); L4 overdue alert does
  **not** resolve/close; original ticket ID preserved; reminder sent exactly once;
  SLA pause blocks escalation and resume shifts the deadline; manual escalation is
  recorded with from/to levels.
- **Routing** (`tests/test_routing.py`): ward-specific officer chosen; unconfigured
  department → `NEEDS_REVIEW` (no random assignment); unknown AI label → review;
  duplicate grouping by category + distance + time without discarding submissions;
  workload balancing prefers the least-loaded officer.
- **Onboarding** (`tests/test_onboarding.py`): single-use code, reuse rejected,
  expired code rejected, unknown code rejected, one Telegram account cannot map to
  two officers, revocation clears the link + closes the mapping, a new code revokes
  older ones, officer action scope (department/level).
- **API** (`tests/test_api_v2.py`): 401 without token; 5 seeded departments;
  officer create/patch; invitation issued; TAT rule upsert; escalation centre;
  overview with 5 departments; CSV + XLSX export (`PK` zip header); RBAC
  (viewer cannot create officers/admins); `/me`.
- **Static checks**: `py_compile` on `api.py`, `bot.py`, `worker.py`,
  `routers/admin.py`, `core/*.py`, `migrate_sheets_to_db.py`; `import api` and
  `import bot` both succeed.

Not covered by automated tests (needs live Telegram + OpenRouter keys): real
callback-button round trips, real verification verdicts, and the Railway smoke test.

---

## 7. Deployment instructions

1. **Database (required for persistence)**
   ```bash
   railway add --database postgres
   ```
   Railway injects `DATABASE_URL`; `postgres://…` is normalised automatically.
   *Without it, data lives in a SQLite file that is wiped on each deploy.*
2. **Worker service (recommended)** — second service from the same repo, start
   command `python worker.py`; set `ENABLE_ESCALATION_SCHEDULER=false` on the API
   service so a single ticker runs.
3. **Environment** — `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `TELEGRAM_BOT_TOKEN`,
   `GOOGLE_SHEETS_CREDENTIALS`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `SECRET_KEY`
   (+ the new vars in section 4).
4. **Deploy** — push to `main`; the Dockerfile installs the new dependencies and
   builds the dashboard as before.
5. **Migrate existing data** (optional, non-destructive):
   ```bash
   python migrate_sheets_to_db.py --dry-run
   python migrate_sheets_to_db.py
   ```
6. **Smoke test**
   ```bash
   curl -s https://<host>/api/health
   TOKEN=$(curl -s -X POST https://<host>/api/login -H 'Content-Type: application/json' \
        -d '{"username":"admin","password":"<ADMIN_PASSWORD>"}' | jq -r .access_token)
   curl -s https://<host>/api/v2/departments -H "Authorization: Bearer $TOKEN"
   ```

---

## 8. Remaining manual configuration

1. **Create officers** (L1–L4 per department) via `POST /api/v2/officers` with their
   ward/block jurisdiction — until then complaints for that department go to
   `NEEDS_REVIEW` (visible in the escalation centre) instead of being assigned.
2. **Link officers' Telegram**: `POST /api/v2/officers/{id}/invitation` → the officer
   sends `/officer GRV-XXXXXXXX` to the bot.
3. **Review TAT hours** per department (`PUT /api/v2/escalation-rules/{department_id}`)
   and fill the district holiday calendar.
4. **Replace the default admin password** (`admin123`) and set a strong `SECRET_KEY`;
   create one account per administrator (`POST /api/v2/admins`).
5. **Keep `BYPASS_LOGIN=false`** in production.
6. **Dashboard UI** for the new modules still has to be built (APIs are ready).


