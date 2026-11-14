from fastapi.testclient import TestClient

from app.db import SessionLocal, init_db
from app.main import app
from app.models import Company, Job

init_db()
client = TestClient(app)


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_export_shape_when_empty():
    db = SessionLocal()  # the app DB is shared across test modules: start clean
    try:
        db.query(Job).delete()
        db.query(Company).delete()
        db.commit()
    finally:
        db.close()
    resp = client.get("/api/export")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 0 and body["jobs"] == []
