"""One-shot refresh + export — what the scheduled job-search runs invoke.

    python -m app.cli [--since <ISO>] [--threshold 60] [--no-ingest]

Runs the registry load and a full ingest of every enabled board
(incremental: conditional fetches keep a no-change run near-free), then
writes the scored, tracker-deduped export to exports/latest.json and
prints a one-line summary. Per-board errors are reported in the summary
but do not fail the run — partial data is still useful; the export's
`since` delta is what the consumer reads.
"""

import argparse
import json
from pathlib import Path

from app.config import settings
from app.db import SessionLocal, init_db
from app.exporting import build_export
from app.ingest import run_ingest
from app.registry import load_companies

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_REGISTRY = _PROJECT_ROOT / "data" / "companies.yaml"
_DEFAULT_OUT = _PROJECT_ROOT / "exports" / "latest.json"


def main() -> int:
    parser = argparse.ArgumentParser(prog="jobradar")
    parser.add_argument("--since", default=None, help="ISO timestamp; delta export only")
    parser.add_argument("--threshold", type=int, default=60)
    parser.add_argument("--no-ingest", action="store_true", help="export from current DB")
    parser.add_argument("--out", default=str(_DEFAULT_OUT))
    args = parser.parse_args()

    init_db()
    db = SessionLocal()
    try:
        load_companies(db, _REGISTRY)
        new_total = changed_total = errors = 0
        if not args.no_ingest:
            stats = run_ingest(db)
            new_total = sum(s.new for s in stats.companies)
            changed_total = sum(s.updated for s in stats.companies)
            errors = sum(1 for s in stats.companies if s.error)
        export = build_export(
            db,
            threshold=args.threshold,
            since=args.since,
            tracker_path=settings.tracker_path,
        )
    finally:
        db.close()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(export, ensure_ascii=False, indent=1), encoding="utf-8")
    print(
        f"ingest: {new_total} new, {changed_total} updated, {errors} board errors | "
        f"export: {export['count']} jobs above {args.threshold} "
        f"({export['excluded_by_tracker']} tracker-suppressed) -> {out_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
