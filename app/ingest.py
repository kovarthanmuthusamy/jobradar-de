"""Ingestion: feed -> upsert by canonical apply URL -> change stats.

The stats are the token-efficiency story: a run where the feed answers 304,
or where every posting hashes to what is already stored, changes nothing and
produces an empty export delta. Only genuinely new/changed rows ever reach
the scored JSON the midday pipeline reads.
"""

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.adapters import ADAPTERS
from app.adapters.base import RawJob, canonicalize_url, http_fetch
from app.models import Company, Job


def _utcnow() -> datetime:
    return datetime.now(UTC)


def content_hash(raw: RawJob) -> str:
    payload = "\x1f".join(
        [raw.title, raw.location_text or "", raw.employment_type or "", raw.description_text]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class CompanyRunStats:
    company: str
    not_modified: bool = False
    new: int = 0
    updated: int = 0
    unchanged: int = 0
    deactivated: int = 0
    error: str | None = None


@dataclass
class IngestStats:
    companies: list[CompanyRunStats] = field(default_factory=list)

    @property
    def total_new(self) -> int:
        return sum(c.new for c in self.companies)

    def to_dict(self) -> dict:
        return {
            "companies": [vars(c) for c in self.companies],
            "total_new": self.total_new,
        }


def ingest_company(db: Session, company: Company, fetcher=http_fetch) -> CompanyRunStats:
    stats = CompanyRunStats(company=company.name)
    adapter = ADAPTERS[company.ats]
    try:
        raw_jobs, fetch = adapter.fetch_jobs(
            company.board_id,
            override=company.feed_url_override,
            etag=company.etag,
            last_modified=company.last_modified,
            fetcher=fetcher,
        )
    except Exception as exc:  # one bad board must never kill the run
        stats.error = str(exc)
        return stats
    company.last_fetched_at = _utcnow()
    if raw_jobs is None:  # 304 — feed unchanged, cheapest possible outcome
        stats.not_modified = True
        company.last_run_new = 0
        db.commit()
        return stats
    company.etag = fetch.etag or company.etag
    company.last_modified = fetch.last_modified or company.last_modified

    seen_urls: set[str] = set()
    for raw in raw_jobs:
        url = canonicalize_url(raw.apply_url)
        seen_urls.add(url)
        digest = content_hash(raw)
        job = db.query(Job).filter(Job.apply_url == url).one_or_none()
        if job is None:
            db.add(
                Job(
                    company_id=company.id,
                    source=adapter.name,
                    external_id=raw.external_id,
                    title=raw.title,
                    location_text=raw.location_text,
                    city=raw.city,
                    country=raw.country or company.country,
                    remote=raw.remote,
                    employment_type=raw.employment_type,
                    apply_url=url,
                    description_text=raw.description_text,
                    posted_at=raw.posted_at,
                    content_hash=digest,
                )
            )
            stats.new += 1
        else:
            job.last_seen_at = _utcnow()
            if not job.is_active:
                job.is_active = True
                stats.updated += 1
            if job.content_hash != digest:
                job.title = raw.title
                job.location_text = raw.location_text
                job.city = raw.city
                job.country = raw.country or company.country
                job.remote = raw.remote
                job.employment_type = raw.employment_type
                job.description_text = raw.description_text
                job.posted_at = raw.posted_at or job.posted_at
                job.content_hash = digest
                stats.updated += 1
            else:
                stats.unchanged += 1
    # Postings that vanished from the feed are closed, not deleted (history matters).
    stale = (
        db.query(Job)
        .filter(
            Job.company_id == company.id,
            Job.is_active.is_(True),
            Job.apply_url.notin_(seen_urls),
        )
        .all()
    )
    for job in stale:
        job.is_active = False
        stats.deactivated += 1
    company.last_run_new = stats.new
    db.commit()
    return stats


def run_ingest(db: Session, fetcher=http_fetch) -> IngestStats:
    stats = IngestStats()
    companies = db.query(Company).filter(Company.enabled.is_(True)).all()
    for company in companies:
        if company.ats in ADAPTERS:
            stats.companies.append(ingest_company(db, company, fetcher=fetcher))
    return stats
