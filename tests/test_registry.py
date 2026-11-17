from pathlib import Path

from app.adapters import ADAPTERS
from app.ingest import run_ingest
from app.models import Company
from app.registry import load_companies

REGISTRY = Path(__file__).parent.parent / "data" / "companies.yaml"


def test_seed_registry_loads(db):
    added = load_companies(db, REGISTRY)
    assert added >= 40
    companies = db.query(Company).all()
    enabled_ats = {c.ats for c in companies if c.enabled}
    assert enabled_ats <= set(ADAPTERS)  # every enabled board has an adapter
    personio_com = [c for c in companies if c.board_id == "twaice"]
    assert personio_com and personio_com[0].feed_url_override.endswith("personio.com/xml")
    by_board = {c.board_id: c for c in companies}
    assert by_board["DeepL"].size_band == "1000+"  # seeded size signal
    assert by_board["twaice"].size_band is None  # unknown stays unknown


def test_ingest_skips_companies_without_adapter(db):
    db.add(Company(name="Pending Co", ats="recruitee", board_id="pending", enabled=True))
    db.commit()
    stats = run_ingest(db, fetcher=lambda *a: None)
    assert stats.companies == []  # no adapter -> skipped, no crash
