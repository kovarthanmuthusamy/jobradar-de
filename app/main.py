"""JobRadar DE API.

The surface stays deliberately small. /api/export is the contract the
12:30/17:30 job-search runs consume: one compact JSON of new, scored,
tracker-deduped postings above threshold — they read this instead of
opening job boards. Pass ?since=<ISO timestamp> for a pure delta.
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db, init_db
from app.exporting import build_export
from app.exporting import job_out as _job_out
from app.ingest import run_ingest
from app.models import Company, Job
from app.scoring import THRESHOLD


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
    return build_export(
        db,
        threshold=threshold,
        since=since,
        include_below=include_below,
        tracker_path=settings.tracker_path,
    )
