# Public Grievance Bot

A Telegram bot + admin dashboard for public grievance reporting. A citizen
sends a photo of a civic issue (pothole, garbage, broken streetlight, etc.);
Gemini Vision (via OpenRouter) validates and classifies it; the citizen shares
their GPS location; a ticket is logged to Google Sheets and the assigned officer
is notified on Telegram. The officer resolves it by replying with an "after"
photo, which notifies the citizen and asks for a rating. A React dashboard
gives admins a map/list view with filters and SLA escalation status.

## Architecture

- `bot.py` — the Telegram bot (citizen + officer conversation flow).
- `sheets.py` — Google Sheets client: ticket read/write, officer directory.
- `api.py` — FastAPI backend serving the dashboard (JWT-protected).
- `auth.py` — admin login + JWT issuing/verification.
- `dashboard/` — React (Vite) admin dashboard.

## Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   cd dashboard && npm install && npm run build && cd ..
   ```

2. **Configure environment variables.** Copy `.env.example` to `.env` (local
   dev only — on a host like Railway, set these in the platform's
   environment variable settings instead) and fill in:
   - `TELEGRAM_BOT_TOKEN` — from [@BotFather](https://t.me/BotFather). The
     bot refuses to start without this; there is no baked-in default.
   - `OPENROUTER_API_KEY` — from [OpenRouter](https://openrouter.ai/keys).
     The photo triage/vision call goes through OpenRouter; without this key
     the bot refuses to start. Optional `OPENROUTER_MODEL` overrides the
     vision model (default `google/gemini-2.0-flash-001`).
   - `GOOGLE_SHEETS_CREDENTIALS` — a Google Cloud service account key
     (JSON, as a single-line string), shared as an **Editor** on the target
     Google Sheet. See "Google Sheet setup" below.
   - `ADMIN_USERNAME` / `ADMIN_PASSWORD` — dashboard login. Change these;
     the code logs a loud warning and falls back to `admin`/`admin123` if
     unset, which is not safe to deploy with.
   - `SECRET_KEY` — random secret for signing dashboard JWTs
     (`openssl rand -hex 32`). Also has an insecure fallback with a logged
     warning — always set this in production.
   - `DEFAULT_OFFICER_CHAT_ID` (optional) — fallback Telegram chat ID for
     categories that don't yet have an officer with a registered chat ID.
   - `ENABLE_OFFICER_NOTIFICATIONS` (optional, default `true`) — kill
     switch for officer Telegram notifications.
   - `CORS_ORIGINS` (optional, default `*`) — comma-separated list of
     allowed dashboard origins.

   See `.env.example` for the full list with comments.

3. **Run**:
   ```bash
   python bot.py          # Telegram bot (separate process)
   uvicorn api:app --reload   # Dashboard API + frontend
   ```
   Or use `start.sh` (used by the `Procfile`/`Dockerfile`) which runs both.

## Logging in to the dashboard

The dashboard uses a **single shared admin login**, read from the
`ADMIN_USERNAME` / `ADMIN_PASSWORD` environment variables (`config.py` loads
a local `.env` file for you). If those are unset, the server falls back to
`admin` / `admin123` and logs a loud security warning at startup — so the
first thing to check when a login is rejected is which of the two the
*running* server actually picked up:

- **Local dev**: copy `.env.example` to `.env` and set `ADMIN_USERNAME` /
  `ADMIN_PASSWORD`. `uvicorn api:app` picks them up automatically.
- **Hosted (Railway etc.)**: set them in the platform's Variables/Config tab
  and redeploy. A local `.env` is gitignored and is **not** uploaded.

Because env vars are read once at startup, restart the API after changing
them. If the login screen says "Cannot reach the API at ...", the backend
isn't running (or `VITE_API_URL` points at the wrong host) — that is a
different failure from a rejected password.

Sessions last 24 hours (`ACCESS_TOKEN_EXPIRE_MINUTES`) and are signed with
`SECRET_KEY`; changing `SECRET_KEY` invalidates every existing session, so
open dashboards bounce back to the login screen.

### Temporarily hiding the login (`BYPASS_LOGIN`)

If you need to get into the dashboard and the login screen is in the way, set
`BYPASS_LOGIN=true` (in `.env` locally, or in the host's Variables tab) and
restart the API. The protected routes then stop requiring a JWT and the
dashboard opens directly. **Nothing is removed:** `Login.jsx`, the password
check, the JWT issuing/verification and the token expiry all stay in the
codebase, they are simply not used while the flag is on. The API logs a loud
security warning at startup and the dashboard header shows a **LOGIN
BYPASSED** badge so it can't be forgotten.

Set `BYPASS_LOGIN=false` (or delete the variable) and restart the API to bring
the login screen back — no code change needed either way. Never leave it on for
a public deployment.

## Google Sheet setup

The app uses one Google Sheet as its database, with two tabs:

### `Sheet1` (tickets — auto-created by the bot)

Headers (auto-inserted on first write): `Ticket ID, Timestamp, Category,
Severity, Status, Officer, Description, Lat, Long, Photo URL, Map Link,
Integrity Metric, Chat ID, PhotoID, After File ID, User Rating, Pin Code,
Area`. You don't need to create this manually.

### `Officer Details` (you must create this tab and populate it)

Columns:

| Column | Meaning |
|---|---|
| `Officer_ID` | Unique ID for the officer (any string, e.g. `DHM-001`). |
| `Full_Name` | Officer's display name. |
| `Mobile` | Contact number (for admin reference; not used by the bot). |
| `Designation` | Job title. |
| `Sector` | Must match a bot category exactly: `Sanitation`, `Drainage`, `Water Supply`, `Road Infra`, `Lighting`, `Fire`, or `Other`. |
| `Zone` | Ward/zone name (for admin reference; routing is currently by Sector only, not Zone — see Known Limitations). |
| `Level` | `1` (or `L1`/`Field`) for the ground-level officer who gets notified first; the escalation contact's `Officer_ID` goes in their `Reports_To`. |
| `Reports_To` | The `Officer_ID` of this officer's escalation contact (their L2). |
| `Sector_Head_ID` | Not currently used by the code; kept for future use. |
| `Telegram_Chat_ID` | **The officer's numeric Telegram chat ID.** Required for them to actually receive notifications — see below. Leave blank if not yet registered; the bot falls back to `DEFAULT_OFFICER_CHAT_ID` (or skips notifying, if that's also unset) and still logs the ticket either way. |

**Getting an officer's Telegram chat ID**: have them open a chat with the
bot and send `/id` — it replies with their numeric chat ID to paste into
the sheet.

Without a `Telegram_Chat_ID` for at least the L1 officer of each active
category, notifications for that category go to `DEFAULT_OFFICER_CHAT_ID`
(if set) or are skipped (the ticket is still logged and visible on the
dashboard either way).

## Deploying

`Dockerfile`/`Procfile`/`start.sh`/`build.sh` are set up for Railway-style
hosting: the API process serves the built dashboard and proxies Telegram
images; the bot runs as a separate worker process. Set all environment
variables above in the host's dashboard before first deploy.

## Known limitations / what's still needed before a public district rollout

- **Telegram-only.** Reach in Dhamtari will be limited by Telegram
  adoption; consider WhatsApp Business API or CSC-operator-assisted filing
  for wider access.
- **English-only bot copy.** Needs Hindi (and ideally
  Chhattisgarhi/Halbi-aware) message text for citizens and officers.
- **Google Sheets as the datastore** works for a pilot but doesn't scale
  well and has no concurrent-write safety; consider migrating to a real
  database (e.g. Postgres) before district-wide volume.
- **Rate-limiting and duplicate-photo detection are in-memory** — reset on
  every restart and don't work across multiple bot processes. Fine for a
  single-instance pilot.
- **Routing is by Sector only**, not Zone/ward — if a sector has multiple
  L1 officers, the last one read from the sheet wins (a warning is logged
  when this happens). For fine-grained ward-level routing, the code would
  need extending to match on Zone too.
- **Telegram `file_id`s are not a durable photo archive** — for
  RTI/audit-grade record-keeping, pull photos into permanent storage
  (S3/GCS) instead of only referencing Telegram's copy.
- **Single shared admin login** — no per-department accounts yet.
- **No citizen consent/privacy notice** about what's collected (GPS,
  photo, Telegram chat ID) and how long it's retained — needed before
  public launch.
- **Verify the Google Sheet's sharing settings** before going live: it
  should be shared only with the service account (Editor) and the specific
  admins who need to see raw ticket data (which includes citizens' GPS
  coordinates and Telegram chat IDs) — not "anyone with the link."
