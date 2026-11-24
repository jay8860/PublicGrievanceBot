"""Standalone TAT/escalation worker.

Deploy this as its own process (Railway worker service, systemd unit, cron...) so
the escalation engine keeps running even if the API container is restarting:

    python worker.py

It uses the same DATABASE_URL as the API and is safe to run alongside the API's
built-in scheduler - every escalation is deduplicated in the database.
"""
import logging
import os
import time

from core.db import SessionLocal, init_db
from core.escalation import run_once
from core.seed import ensure_seed

TICK_SECONDS = int(os.getenv("ESCALATION_TICK_SECONDS", "300"))


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    log = logging.getLogger("tat-worker")

    url = init_db()
    db = SessionLocal()
    try:
        ensure_seed(db)
    finally:
        db.close()

    log.info("TAT worker started (db=%s, tick=%ss)", url, TICK_SECONDS)
    while True:
        db = SessionLocal()
        try:
            summary = run_once(db)
            if any(summary.values()):
                log.info("tick: %s", summary)
        except Exception as exc:            # keep the worker alive
            log.exception("tick failed: %s", exc)
        finally:
            db.close()
        time.sleep(TICK_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("stopped")
