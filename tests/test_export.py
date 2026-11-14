from fastapi.testclient import TestClient

from app.db import SessionLocal, init_db
from app.main import app
from app.models import Company, Job

init_db()
client = TestClient(app)


def _seed() -> None:
    db = SessionLocal()
    try:
        db.query(Job).delete()
        db.query(Company).delete()
        company = Company(name="Export Co", ats="personio", board_id="export-co", country="Germany")
        db.add(company)
        db.flush()
        db.add_all(
            [
                Job(
                    company_id=company.id, source="personio", external_id="e1",
                    title="Machine Learning Engineer", location_text="Berlin", city="Berlin",
                    country="Germany", employment_type="full-time permanent",
                    apply_url="https://export-co.jobs.personio.de/job/e1",
                    description_text="Python, PyTorch, FastAPI, Docker, Kubernetes, LLM, RAG.",
                    content_hash="a",
                ),
                Job(
                    company_id=company.id, source="personio", external_id="e2",
                    title="Office Manager", location_text="Berlin", city="Berlin",
                    country="Germany", employment_type="full-time permanent",
                    apply_url="https://export-co.jobs.personio.de/job/e2",
                    description_text="Scheduling and office organization.",
                    content_hash="b",
                ),
            ]
        )
        db.commit()
    finally:
        db.close()


def test_export_filters_below_threshold_and_adds_scores():
    _seed()
    body = client.get("/api/export").json()
    assert body["count"] == 1
    job = body["jobs"][0]
    assert job["title"] == "Machine Learning Engineer"
    assert job["score"] > 60
    assert set(job["breakdown"]) == {"role", "location", "seniority", "german", "type"}
    assert "description_text" not in job  # compact: no descriptions in the export


def test_export_include_below_returns_everything():
    _seed()
    body = client.get("/api/export?include_below=true").json()
    assert body["count"] == 2
