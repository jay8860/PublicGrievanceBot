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
| **Before/after AI verification** | On resolution the backend fetches the original Telegram photo + the after photo and asks OpenRouter for `{same_location, issue_addressed, confidence, verdict}` with guard rails (verified only if same location **and** confidence ≥ 0.7). **Verified → auto-approved** (status `VERIFIED`, logged as `verification_auto_approved` by `ai-verifier`, citizen told it was photo-verified). Anything the AI can't decide — no key, network/JSON error, missing photo, different location, issue still visible — stays `RESOLVED` and lands in the **Resolution Verification** queue for a human. `AUTO_APPROVE_AI_RESOLUTION=false` disables the automatic step. |

| **Citizen feedback / reopening** | Confirm (→ CLOSED) or "still broken" (→ REOPENED, TAT restarts at L1, full history preserved). |
| **Duplicate grouping** | Same category + ≤ 500 m + ≤ 72 h → linked into one `group_id`. Every citizen submission is preserved (nothing discarded). |
| **Audit logging** | Every privileged mutation writes `audit_logs` (actor, action, entity, detail). |
| **Admin accounts (RBAC)** | Individual admin users (`superadmin` / `admin` / `viewer`) with bcrypt hashes; the legacy env admin still works and is bootstrapped as a `superadmin`. Role checks on every v2 endpoint. |
| **Reports** | CSV and Excel (`.xlsx`) export with department + date-range filters. |
| **Analytics APIs** | Overview KPIs (total/new/pending/resolved/overdue/escalated/avg resolution time/department table), officer performance, geo points for the map, escalation-centre buckets. |
| **Migration** | `migrate_sheets_to_db.py` imports officers + tickets (IDs, chat IDs, photo file IDs, ratings) idempotently, without deleting anything and without sending notifications. |

### Deliberately NOT done yet (do not assume these exist)

1. **PostgreSQL is supported but not provisioned.** Without `DATABASE_URL` the app
   uses a SQLite file inside the container, which is **wiped on every deploy**.
2. **Object storage (S3/GCS)** — photos are still referenced by Telegram `file_id`;
   AI verification downloads them on demand.
3. **Redis/BullMQ** — scheduling uses APScheduler in-process + `worker.py`
   (safe on one node because escalations are deduplicated in the DB).
4. **Hindi/Chhattisgarhi bot copy**, multi-photo complaints, ward-boundary polygons,
   perceptual-hash image dedupe.
5. **Officer dashboard login** (JWT with `role=officer`) — RBAC primitives exist, but
   officers currently act through Telegram only.
6. **Automated browser E2E (Playwright)** — page renders + every backend workflow are
   tested (see §9), but there is no headless-browser suite in the repo yet.



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
| `AUTO_APPROVE_AI_RESOLUTION` | `true` | AI-verified resolutions close themselves (status `VERIFIED`). `false` sends every resolution to the manual queue. |

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
| `GET /analytics/dashboard` | admin | Overview KPIs, trend, distributions, recents, critical list |
| `GET /analytics/trends`, `GET /analytics/wards` | admin | Monthly and ward-level analytics |
| `GET /analytics/officer-performance` | admin | Officer scorecard including citizen ratings |
| `GET /verifications`, `POST /complaints/{id}/verification` | admin | Verification queue + approve/reject/review/reopen |
| `GET /security-status` | superadmin | Live security/config panel for Settings |
| `POST /admins/me/password` | any admin | Change own password |


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

**Frontend verification (performed on this machine)**

- `vite build` → **success**, 2,280 modules, `dist/assets/index-5ED9uaYf.js` 892 kB
  (254 kB gzip) + 42.7 kB CSS. No runtime dependency was added.
- **Page render smoke test** (`dashboard/ssr-smoke.jsx`, built with `vite build --ssr`):
  all **10 non-map pages render without errors** ("ALL 10 PAGE RENDERS PASSED").
  The map page needs a real DOM, so it is covered by the build + API contract only.
- **Dev server**: `vite --port 5199` served `/` (200), `/src/main.jsx` (200) and
  `/src/pages/Officers.jsx` (200), i.e. every page transforms cleanly in dev mode.
- **Prop guard** (`node checks/component-props.mjs`): fails if a page renders
  `token` or `onNavigate` without destructuring it. This caught a real crash —
  `Complaints` rendered `<ComplaintDrawer token={token} />` although the component
  took no props (the earlier smoke test missed it because the page returned its
  loading state before reaching that JSX). Now passes on the fixed tree.
- **Complaints regression render** (`checks/ssr-complaints.jsx`, mocked rows):
  `OK: Complaints rendered with data (13295 chars)`. Reverting the signature makes it
  fail with the original `token is not defined`, so the same crash cannot return
  unnoticed. Page-level render errors are also contained by `ErrorBoundary`.

- **End-to-end workflow test** (`scripts/e2e_dashboard.py`, run against the local API
  with the demo dataset) exercised exactly what the UI calls:
  login → me → departments → categories → **create officer** → **invitation code** →
  code history → **assign** (NEEDS_REVIEW → ASSIGNED) → **acknowledge** (ACKNOWLEDGED)
  → **in progress** (IN_PROGRESS) → **escalate** (L2) → verify queue →
  **approve verification** (VERIFIED) → dashboard/performance/wards/trends/centre/geo
  analytics → **CSV export** (1,769 B) → **XLSX export** (6,249 B, valid zip) →
  **audit log** (9 entries) → **security status** → **wrong-password rejection** (400).
- Two real defects were found by these tests and fixed: assignment left a
  `NEEDS_REVIEW` complaint unchanged when it carried an `acknowledged_at`
  (regression test added), and the fallback TAT rule had `None` hours before being
  flushed (assignment of an unclassified complaint crashed).

Not covered: real Telegram callback round trips, live OpenRouter verdicts, and the
Railway smoke test (needs the deployed bot token + AI key). No headless-browser
screenshot suite is included; the walkthrough in §9 describes each screen.

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
6. Review the new portal with real data (`python scripts/seed_demo.py` seeds a demo dataset).

---

## 9. Frontend — District Grievance Management portal

The dashboard was rebuilt (React 18 + Vite + Tailwind, no new runtime dependencies)
as a sidebar admin portal. The visual direction — a warm-paper **district register**
with one ink-navy accent, hairline rules, serif page titles, mono ticket references
and tabular figures — is written down in `dashboard/DESIGN.md`; the Tailwind theme
(`dashboard/tailwind.config.js`) carries the neutral ramps, radii, type stack and
shadow scale so the direction is enforced, not improvised per screen.
**11 working pages**, all wired to `/api/v2`:


| Page | What it does | Backing endpoints |
|---|---|---|
| **Overview** | 8 KPI tiles, created-vs-resolved trend, status donut, department bar chart, recent complaints/escalations, critical list | `/analytics/dashboard` |
| **Complaints** | Search + 7 filters, sortable paginated table with photos, complaint drawer (evidence, map link, AI fields, history, escalation timeline, feedback) and actions: assign / acknowledge / progress / escalate / pause / resume / resolve / reopen | `/complaints`, `/complaints/{id}`, `/officers`, action endpoints |
| **Departments** | 5 department cards with live counts, edit, category manager (add/list), TAT policy editor (hours, working days, holidays), officer roster | `/departments`, `/categories`, `/escalation-rules` |
| **Officer Management** | Officer table (ID, name, designation, department, L1–L4, jurisdiction, Telegram state, pending, status), add/edit form (mobile, email, reporting officer, jurisdiction), invitation-code modal with copy + expiry, revoke Telegram, activate/deactivate, and a visual L1–L4 hierarchy per department | `/officers`, `/officers/{id}/invitation`, `/revoke-telegram`, `/codes` |
| **Escalation Centre** | Tabs for L1/L2/L3/L4 pending + overdue / unacknowledged / reopened / needs-review, department + priority filters, manual escalate | `/escalation-centre`, `/complaints/{id}/escalate` |
| **Geographic Monitoring** | Leaflet map with severity-coloured markers, grid clustering, density overlay, ward hotspot list, department/severity/status/level filters, popup → drawer | `/analytics/geo`, `/analytics/wards` |
| **Resolution Verification** | Before/after image comparison, AI verdict badge, citizen feedback, approve / reject / manual review / reopen with an audit note | `/verifications`, `/complaints/{id}/verification` |
| **Officer Performance** | Workload chart, scorecard (assigned/resolved/pending/overdue, ack time, resolution time, escalation rate, ★ rating), department + level filters | `/analytics/officer-performance` |
| **Reports & Analytics** | Dept/date export (CSV + Excel), KPI summary, monthly trend, ward chart, department table | `/reports/complaints`, `/analytics/trends`, `/analytics/wards`, `/analytics/overview` |
| **Audit Logs** | Searchable trail with action, record, actor, source (Dashboard/Officer/Citizen/System) and detail snapshot | `/audit-logs` |
| **Settings** | Own account + password change, system/security flags (DB, secret default, default password, bypass, scheduler, tokens), administrator accounts (create/deactivate, superadmin only) | `/me`, `/admins/me/password`, `/security-status`, `/admins` |

**Frontend architecture**

```
dashboard/src/
  App.jsx                  hash router + auth gate + role guard + layout
  lib/                     utils (JWT decode, dates, TAT labels), nav definition
  services/apiV2.js        single API layer (reuses the existing axios instance)
  hooks/                    useFetch (loading/error/reload), useConfirmDialog
  components/              Layout(sidebar+header), ErrorBoundary, ui (cards/badges),
                           controls, overlays (modal/confirm/tabs/pagination),
                           DataTable, Charts (recharts), Toast, ComplaintDrawer,
                           ComplaintMap, ImageCompare, feedback states
  checks/                  component-props.mjs (prop guard), ssr-complaints.jsx
                           (page regression render with mocked data)
  pages/                   11 pages listed above
```

* Every page implements loading, empty and error states; mutations show toasts and
  refresh their data; destructive actions require a confirmation dialog.
* A page-level `ErrorBoundary` keeps a render error inside the content area instead
  of blanking the portal.

* Role-based UI: viewers see read-only pages and no admin sections; superadmin-only
  settings render a clear notice for other roles.
* Images are fetched with the JWT (existing `AuthImage`), never as bare URLs.
* No mock data and no dead buttons: every control calls a real endpoint.



