"""JobRadar DE API.

The surface stays deliberately small. /api/export is the contract the
12:30/17:30 job-search runs consume: one compact JSON of active postings,
newest first — they read this file instead of opening job boards.
(Score fields join this payload in the scoring step.)
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db, init_db
from app.ingest import run_ingest
from app.models import Company, Job


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
def export(db: Session = Depends(get_db)) -> dict:
    """Compact delta-ready export: active jobs only, no descriptions, newest first."""
    jobs = (
        db.query(Job)
        .filter(Job.is_active.is_(True))
        .order_by(Job.posted_at.desc().nullslast(), Job.first_seen_at.desc())
        .all()
    )
    return {"count": len(jobs), "jobs": [_job_out(j) for j in jobs]}
