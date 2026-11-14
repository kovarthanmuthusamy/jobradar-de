from datetime import UTC, datetime
from pathlib import Path

from app.adapters.base import canonicalize_url
from app.adapters.personio import PersonioAdapter

FIXTURE = Path(__file__).parent / "fixtures" / "personio_sample.xml"


def test_parse_fixture_fields():
    jobs = PersonioAdapter().parse_board(FIXTURE.read_bytes(), "example-gmbh")
    assert len(jobs) == 2
    ml = jobs[0]
    assert ml.external_id == "2211334"
    assert ml.title == "Machine Learning Engineer (m/f/d)"
    assert ml.apply_url == "https://example-gmbh.jobs.personio.de/job/2211334"
    assert ml.city == "Berlin"
    assert ml.location_text == "Berlin, Munich"
    assert ml.employment_type == "full-time permanent"
    assert ml.posted_at == datetime(2026, 11, 12, 9, 30, tzinfo=UTC)
    # HTML is stripped to plain text for storage/scoring.
    assert "<p>" not in ml.description_text and "LLM agents" in ml.description_text
    assert "German B2 is a plus" in ml.description_text


def test_parse_second_position():
    jobs = PersonioAdapter().parse_board(FIXTURE.read_bytes(), "example-gmbh")
    ws = jobs[1]
    assert ws.title.startswith("Working Student")
    assert ws.city == "Munich"
    assert ws.employment_type == "part-time intern"


def test_feed_url_and_override():
    adapter = PersonioAdapter()
    assert adapter.feed_url("acme") == "https://acme.jobs.personio.de/xml"
    assert adapter.feed_url("acme", "https://example.com/feed.xml") == "https://example.com/feed.xml"


def test_canonicalize_url_strips_tracking():
    url = "https://Example.jobs.personio.de/job/123/?utm_source=linkedin&ref=x"
    assert canonicalize_url(url) == "https://example.jobs.personio.de/job/123"
