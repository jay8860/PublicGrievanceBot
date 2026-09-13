# Public Grievance Bot

A Telegram bot + admin dashboard for public grievance reporting. A citizen
sends a photo of a civic issue (pothole, garbage, broken streetlight, etc.);
Gemini Vision validates and classifies it; the citizen shares their GPS
location; a ticket is logged to Google Sheets and the assigned officer is
notified on Telegram. The officer resolves it by replying with an "after"
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
   - `GOOGLE_API_KEY` (or `GEMINI_API_KEY`) — from
     [Google AI Studio](https://aistudio.google.com/apikey).
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
