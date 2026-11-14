"""JobRadar DE API.

The surface stays deliberately small. /api/export is the contract the
12:30/17:30 job-search runs consume: one compact JSON of new, scored,
tracker-deduped postings above threshold — they read this instead of
opening job boards. Pass ?since=<ISO timestamp> for a pure delta.
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db, init_db
from app.ingest import run_ingest
from app.models import Company, Job
from app.scoring import THRESHOLD, score_job
from app.tracker import is_tracker_match, load_tracker_keys


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="JobRadar DE", version="0.1.0", lifespan=lifespan)


class CompanyIn(BaseModel):
    name: str
    ats: str
    board_id: str
    feed_url: str | None = None
    careers_url: str | None = None
    country: str | None = None
    enabled: bool = True


def _company_out(c: Company) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "ats": c.ats,
        "board_id": c.board_id,
        "careers_url": c.careers_url,
        "country": c.country,
        "enabled": c.enabled,
        "last_fetched_at": c.last_fetched_at.isoformat() if c.last_fetched_at else None,
        "last_run_new": c.last_run_new,
    }


def _job_out(j: Job) -> dict:
    return {
        "id": j.id,
        "company": j.company.name,
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


_STATIC_INDEX = Path(__file__).parent / "static" / "index.html"


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse(_STATIC_INDEX)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/companies")
def list_companies(db: Session = Depends(get_db)) -> list[dict]:
    return [_company_out(c) for c in db.query(Company).order_by(Company.name).all()]


@app.post("/api/companies", status_code=201)
def create_company(payload: CompanyIn, db: Session = Depends(get_db)) -> dict:
    company = Company(
        name=payload.name,
        ats=payload.ats,
        board_id=payload.board_id,
        feed_url_override=payload.feed_url,
        careers_url=payload.careers_url,
        country=payload.country,
        enabled=payload.enabled,
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return _company_out(company)


@app.get("/api/jobs")
def list_jobs(active_only: bool = True, db: Session = Depends(get_db)) -> list[dict]:
    q = db.query(Job)
    if active_only:
        q = q.filter(Job.is_active.is_(True))
    return [_job_out(j) for j in q.order_by(Job.first_seen_at.desc()).all()]


@app.post("/api/ingest/run")
def ingest_run(db: Session = Depends(get_db)) -> dict:
    return run_ingest(db).to_dict()


@app.get("/api/export")
def export(
    threshold: int = THRESHOLD,
    since: str | None = None,
    include_below: bool = False,
    db: Session = Depends(get_db),
) -> dict:
    """Scored delta export: active, tracker-deduped, above threshold, no descriptions."""
    q = db.query(Job).filter(Job.is_active.is_(True))
    if since:
        since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        if since_dt.tzinfo is None:
            since_dt = since_dt.replace(tzinfo=UTC)
        q = q.filter(Job.first_seen_at > since_dt)
    jobs = q.order_by(Job.posted_at.desc().nullslast(), Job.first_seen_at.desc()).all()

    tracker_index = None
    if settings.tracker_path and Path(settings.tracker_path).exists():
        tracker_index = load_tracker_keys(settings.tracker_path)

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
        entry = _job_out(job)
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
