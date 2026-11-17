"""The scored export — the contract the job-search pipeline consumes.

One compact JSON: active postings, tracker-deduped (already applied /
rejected roles never resurface), scored with the standing rules, above
threshold, no descriptions. Used by GET /api/export and by the CLI the
scheduled midday runs invoke.
"""

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Job
from app.scoring import THRESHOLD, score_job
from app.tracker import is_tracker_match, load_tracker_keys


def job_out(j: Job) -> dict:
    return {
        "id": j.id,
        "company": j.company.name,
        "company_size_band": j.company.size_band,
        "title": j.title,
        "location": j.location_text,
        "city": j.city,
        "country": j.country,
        "remote": j.remote,
        "employment_type": j.employment_type,
        "posted_at": j.posted_at.isoformat() if j.posted_at else None,
        "apply_url": j.apply_url,
        "source": j.source,
        "first_seen_at": j.first_seen_at.isoformat() if j.first_seen_at else None,
        "is_active": j.is_active,
    }


def build_export(
    db: Session,
    *,
    threshold: int = THRESHOLD,
    since: str | None = None,
    include_below: bool = False,
    tracker_path: str | None = None,
) -> dict:
    q = db.query(Job).filter(Job.is_active.is_(True))
    if since:
        since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        if since_dt.tzinfo is None:
            since_dt = since_dt.replace(tzinfo=UTC)
        q = q.filter(Job.first_seen_at > since_dt)
    jobs = q.order_by(Job.posted_at.desc().nullslast(), Job.first_seen_at.desc()).all()

    tracker_index = None
    if tracker_path and Path(tracker_path).exists():
        tracker_index = load_tracker_keys(tracker_path)

    out: list[dict] = []
    excluded = 0
    for job in jobs:
        if tracker_index and is_tracker_match(
            tracker_index, job.company.name, job.title, job.apply_url
        ):
            excluded += 1
            continue
        result = score_job(job)
        if not include_below and not (result.total > threshold and not result.flags):
            continue
        entry = job_out(job)
        entry["score"] = result.total
        entry["breakdown"] = result.breakdown
        entry["flags"] = result.flags
        out.append(entry)
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "threshold": threshold,
        "tracker_dedupe": bool(tracker_index),
        "excluded_by_tracker": excluded,
        "count": len(out),
        "jobs": out,
    }
