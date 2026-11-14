from fastapi.testclient import TestClient

from app.db import init_db
from app.main import app

init_db()
client = TestClient(app)


def test_dashboard_is_served_at_root():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "JobRadar DE" in resp.text
    assert "/api/export" in resp.text  # the page reads the scored export
