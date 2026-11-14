"""Direct tests for the shared export builder behind /api/export and the CLI."""

from app.db import SessionLocal, init_db
from app.exporting import build_export
from app.models import Company, Job

init_db()


def _seed() -> None:
    db = SessionLocal()
    try:
        db.query(Job).delete()
        db.query(Company).delete()
        company = Company(
            name="Exporting Co", ats="personio", board_id="exporting-co", country="Germany"
        )
        db.add(company)
        db.flush()
        db.add(
            Job(
                company_id=company.id,
                source="personio",
                external_id="x1",
                title="Machine Learning Engineer",
                location_text="Berlin",
                city="Berlin",
                country="Germany",
                employment_type="full-time permanent",
                apply_url="https://exporting-co.jobs.personio.de/job/x1",
                description_text="Python, PyTorch, FastAPI, Docker, Kubernetes, LLM, RAG.",
                content_hash="x",
            )
        )
        db.commit()
    finally:
        db.close()


def test_build_export_matches_endpoint_contract():
    _seed()
    db = SessionLocal()
    try:
        body = build_export(db, threshold=60)
    finally:
        db.close()
    assert body["threshold"] == 60
    assert body["tracker_dedupe"] is False  # no tracker path passed
    assert body["count"] == 1
    assert body["jobs"][0]["score"] > 60
    assert "description" not in body["jobs"][0]


def test_build_export_since_in_future_is_empty():
    _seed()
    db = SessionLocal()
    try:
        body = build_export(db, since="2999-01-01T00:00:00Z")
    finally:
        db.close()
    assert body["count"] == 0
