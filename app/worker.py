"""Ingestion worker: run all enabled feeds on an interval. Nothing else.

Kept separate from the API so a run costs exactly one conditional GET per
board and zero LLM/browser work; most ticks end in 304s and an empty delta.
"""

import time

from app.config import settings
from app.db import SessionLocal, init_db
from app.ingest import run_ingest


def main() -> None:
    init_db()
    while True:
        db = SessionLocal()
        try:
            stats = run_ingest(db)
            print(
                f"ingest: {len(stats.companies)} companies, {stats.total_new} new",
                flush=True,
            )
        finally:
            db.close()
        time.sleep(settings.ingest_interval_seconds)


if __name__ == "__main__":
    main()
