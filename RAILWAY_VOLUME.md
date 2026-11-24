# Running the platform entirely on a Railway volume

Everything the district platform needs — the ticket database **and** the
before/after photos — can live on one Railway volume. No Postgres, no S3, no
extra services.

```
/data                          <- Railway volume mount point
├── grievance.db               <- all platform tables (SQLite)
├── grievance.db-wal           <- SQLite write-ahead log (normal, leave it)
├── grievance.db-shm           <- SQLite shared-memory index (normal)
├── media/photos/2026/         <- archived before/after JPEGs
└── backup-20261124-0930.db    <- snapshots you create (see §8)
```

---

## 1. Create the volume

1. Railway → your project → the **web** service (the one running `start.sh`,
   which runs `uvicorn api:app` and `bot.py` together).
2. Service → **Settings → Volumes → Create Volume** (or right-click the service
   in the canvas → *Attach Volume*).
3. Mount path: **`/data`** — exactly this, the variables below depend on it.

Two facts that matter:

* A volume belongs to **one** service. It cannot be mounted by a second service,
  so the API and the bot must keep running in the same container (`start.sh`
  already does that).
* Deploys on a service with a volume restart the container instead of doing a
  zero-downtime swap. A few seconds of downtime per deploy is normal.

---

## 2. Environment variables

Service → **Variables**. Everything below is a plain value except the token/key
values you already own.

| Variable | Value | Why |
|---|---|---|
| `DATABASE_URL` | `sqlite:////data/grievance.db` | absolute path on the volume |
| `MEDIA_ROOT` | `/data/media` | archived photos folder |
| `SECRET_KEY` | `openssl rand -hex 32` output | signs dashboard JWTs |
| `ADMIN_USERNAME` | e.g. `collector` | bootstrapped superadmin |
| `ADMIN_PASSWORD` | long, unique | do not leave `admin123` |
| `TELEGRAM_BOT_TOKEN` | BotFather token | bot + photo proxy |
| `OPENROUTER_API_KEY` | `sk-or-...` | photo triage + resolution check |
| `OPENROUTER_MODEL` | `google/gemini-2.0-flash-001` | must accept images |
| `PLATFORM_DB_ENABLED` | `true` | mirror bot complaints into the DB |
| `ENABLE_ESCALATION_SCHEDULER` | `true` | TAT tick runs inside the API |
| `ESCALATION_TICK_SECONDS` | `300` | check every 5 min |
| `AUTO_APPROVE_AI_RESOLUTION` | `true` | verified fixes close themselves |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | 24 h dashboard session |
| `BYPASS_LOGIN` | `false` | keep the login screen |
| `CORS_ORIGINS` | `https://your-domain.up.railway.app` | lock CORS down |
| `TICKET_PREFIX` | `GRV` | `GRV-2026-000001` |

**Four slashes on purpose.** `sqlite:////data/grievance.db` = `sqlite://` + the
absolute path `/data/grievance.db`. Three slashes (`sqlite:///data/...`) is a
*relative* path, which resolves to `/app/data/...` inside the container — off the
volume, wiped on the next deploy.

---

## 3. First boot creates the database for you

There is no "create database" step. On startup `api.py` runs:


---

## 4. Photos: what is saved and where

`MEDIA_ROOT` switches on archiving in `core/media.py`:

* **Citizen photo** — saved when the complaint is created. If the bot only hands
  over a Telegram `file_id`, the bytes are pulled from Telegram once and written
  to the volume.
* **Officer's after photo** — saved when the resolution is submitted. The same
  pass also backfills the *original* photo for older tickets, because both
  images are downloaded for the AI comparison anyway.
* **Layout** — `photos/<year>/<TICKET>-<kind>-<hash12>.jpg`. The hash makes the
  write idempotent; ticket refs are sanitised, so a weird ref cannot escape the
  folder.
* **Serving** — `GET /api/v2/complaints/{id}/images/{original|resolution}`,
  JWT-protected, streams the file from disk. The dashboard (complaint drawer,
  complaints table, verification page) prefers this and falls back to the legacy
  `/api/image/{file_id}` Telegram proxy for rows that were never archived.
* **Failure is never fatal** — a read-only or full volume logs a warning and the
  complaint is still saved, just without a local copy.

Sizing: a Telegram photo is roughly 150–300 KB, so **1 GB ≈ 3,000–6,000
complaints** with both photos. Start at 5 GB and watch it.

Old tickets (created before the volume existed) keep working through the
Telegram proxy; their photos move onto the volume the next time that complaint
is resolved. There is no bulk backfill script — Telegram may not even still hold
those files.

---

## 5. Bring the Google Sheets history across

In the service terminal (needs `GOOGLE_SHEETS_CREDENTIALS` set):

```bash
python migrate_sheets_to_db.py --dry-run    # report only, writes nothing
python migrate_sheets_to_db.py              # writes to $DATABASE_URL
```

Idempotent on ticket ref (re-running never duplicates), non-destructive to the
sheet, and it sends no Telegram messages.

---

## 6. Demo data (staging only)

```bash
python scripts/seed_demo.py
```

It writes to whatever `DATABASE_URL` points at — on a Railway shell that is your
**production** volume. Use a separate service/staging volume for demos.

---

## 7. Two writers on one SQLite file

The API and the bot both write, from the same container. `core/db.py` therefore
sets `PRAGMA journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=30000` and a
30 s connect timeout, which is what keeps a concurrent insert from failing with
`database is locked`.

Rules that keep it healthy:

* **Replicas = 1.** SQLite on a volume cannot be shared by two containers. Do
  not scale the web service horizontally.
* **Do not add a second service on this volume** (Railway will not allow it
  anyway). If you want `worker.py` as its own service, point it at Postgres.
* The in-API scheduler (`ENABLE_ESCALATION_SCHEDULER=true`) is enough for a
  district deployment; `worker.py` is optional redundancy.

---

## 8. Backups (do this on day one)

Snapshots use SQLite's online backup API, so they are consistent even while the
bot writes. Run in the service terminal:

```bash
python -c "import sqlite3,time; s=sqlite3.connect('/data/grievance.db'); d=sqlite3.connect('/data/backup-'+time.strftime('%Y%m%d-%H%M')+'.db'); s.backup(d); d.close(); s.close(); print('snapshot written')"
```

Keep a week's worth and prune the rest:

```bash
ls -1t /data/backup-*.db | tail -n +8 | xargs -r rm --
```

Copy a snapshot off the platform by streaming it out of the container and
decoding it locally:

```bash
railway ssh                                                 # in the container
base64 -w0 /data/backup-20261124-0930.db                     # copy the output
# your machine:
echo '<paste>' | base64 -d > grievance-2026-11-24.db
```

**Restore:** stop the service (so nothing is writing) → replace
`/data/grievance.db` with the snapshot → delete `/data/grievance.db-wal` and
`/data/grievance.db-shm` → start the service. Leaving a stale `-wal` behind is
the usual cause of "I restored but the data looks half-old".

Photos are plain files; back them up the same way:

```bash
tar czf /data/media-$(date +%F).tgz /data/media/photos
```

Reports can also be exported any time from the dashboard (CSV/XLSX), which is a
poor-man's logical backup of the complaints table.

---

## 9. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `unable to open database file` | path typo, or volume not mounted at `/data` | `ls /data`; re-check the four slashes |
| `attempt to write a readonly database` | volume mounted read-only / ownership | container runs as root by default — remove any custom `USER` |
| `database is locked` | two containers on the same file (replicas > 1) | set replicas back to 1 |
| Data resets after each deploy | `DATABASE_URL` empty → `/app/grievance.db` | set it to the `/data` path |
| Photos 404 in the drawer | `MEDIA_ROOT` unset, or the ticket predates the volume | check `stored` in `GET /api/v2/complaints/{id}`; set `MEDIA_ROOT` and redeploy |
| Dashboard login rejects everything | `ADMIN_PASSWORD` changed after the first boot | the seeded user keeps its original hash — change the password in the dashboard, not by editing the env var |
| Bot silent, dashboard fine | `TELEGRAM_BOT_TOKEN` missing | set it; `bot.py` exits without it |

---

## 10. When this stops being enough

Move to Postgres (`DATABASE_URL=postgresql://...`, Railway's plugin) and keep
the volume for photos only, when you need any of:

* more than one web replica,
* a separate worker service,
* point-in-time-restore backups,
* comfortably past ~50,000 complaints.

The code path does not change — `core/db.py` already normalises `postgres://`
URLs, and `MEDIA_ROOT` keeps working exactly as above.

1. `init_db()` → `Base.metadata.create_all()` — creates every missing table
   (additive only; it never drops or rewrites an existing one).
2. `ensure_seed(db)` — inserts the 5 departments, their categories and default
   TAT rules, and bootstraps the superadmin from `ADMIN_USERNAME` /
   `ADMIN_PASSWORD`, all only if missing. Safe on every restart.

So: set the variables → deploy → open the URL → log in with `ADMIN_USERNAME` /
`ADMIN_PASSWORD` → the dashboard is live with empty tables.

**Check it landed on the volume** (service → ⋮ → *Terminal*, or `railway ssh`):

```bash
ls -l /data
# grievance.db  grievance.db-wal  grievance.db-shm   (media/ appears after the first photo)
python -c "import sqlite3;c=sqlite3.connect('/data/grievance.db');print(c.execute('select count(*) from departments').fetchone())"
# (5,)
```

Then redeploy once and confirm your ticket count is unchanged — that is the
proof the volume, not the container, is holding the data.
