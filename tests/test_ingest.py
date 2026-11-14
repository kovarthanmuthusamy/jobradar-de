from pathlib import Path

from app.adapters.base import FetchResult
from app.ingest import ingest_company
from app.models import Company, Job

FIXTURE = (Path(__file__).parent / "fixtures" / "personio_sample.xml").read_bytes()


def _company(db) -> Company:
    company = Company(
        name="Example GmbH", ats="personio", board_id="example-gmbh", country="Germany"
    )
    db.add(company)
    db.commit()
    return company


def _fetcher_ok(content=FIXTURE, etag='"v1"'):
    def fetch(url, etag_, last_modified):
        return FetchResult(status_code=200, content=content, etag=etag)

    return fetch


def test_first_ingest_creates_jobs(db):
    stats = ingest_company(db, _company(db), fetcher=_fetcher_ok())
    assert stats.new == 2 and stats.error is None
    assert db.query(Job).count() == 2


def test_second_ingest_is_fully_idempotent(db):
    company = _company(db)
    ingest_company(db, company, fetcher=_fetcher_ok())
    stats = ingest_company(db, company, fetcher=_fetcher_ok())
    assert stats.new == 0 and stats.updated == 0 and stats.unchanged == 2
    assert db.query(Job).count() == 2


def test_304_short_circuits(db):
    company = _company(db)
    ingest_company(db, company, fetcher=_fetcher_ok())

    def fetch_304(url, etag, last_modified):
        assert etag == '"v1"'  # stored ETag is sent back as If-None-Match value
        return FetchResult(status_code=304)

    stats = ingest_company(db, company, fetcher=fetch_304)
    assert stats.not_modified is True and stats.new == 0


def test_vanished_job_is_deactivated_not_deleted(db):
    company = _company(db)
    ingest_company(db, company, fetcher=_fetcher_ok())
    parts = FIXTURE.split(b"<position>")
    one_job = parts[0] + b"<position>" + parts[1] + b"</workzag-jobs>"
    stats = ingest_company(db, company, fetcher=_fetcher_ok(content=one_job, etag='"v2"'))
    assert stats.deactivated == 1
    assert db.query(Job).count() == 2
    assert db.query(Job).filter(Job.is_active.is_(False)).count() == 1


def test_changed_description_counts_as_update(db):
    company = _company(db)
    ingest_company(db, company, fetcher=_fetcher_ok())
    changed = FIXTURE.replace(b"LLM agents", b"AI agents")
    stats = ingest_company(db, company, fetcher=_fetcher_ok(content=changed, etag='"v2"'))
    assert stats.updated == 1 and stats.new == 0
