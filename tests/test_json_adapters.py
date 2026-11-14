from datetime import UTC, datetime
from pathlib import Path

from app.adapters import ADAPTERS
from app.adapters.ashby import AshbyAdapter
from app.adapters.greenhouse import GreenhouseAdapter
from app.adapters.lever import LeverAdapter

FIXTURES = Path(__file__).parent / "fixtures"


def test_all_spec_adapters_registered():
    assert set(ADAPTERS) == {"personio", "ashby", "greenhouse", "lever"}


def test_ashby_parse():
    jobs = AshbyAdapter().parse((FIXTURES / "ashby_sample.json").read_bytes())
    assert len(jobs) == 2
    first = jobs[0]
    assert first.title == "AI Engineer — Agents"
    assert first.city == "Berlin"
    assert first.remote is False
    assert first.employment_type == "FullTime"
    assert first.apply_url.endswith("/application")
    assert first.posted_at == datetime(2026, 11, 13, 8, 15, tzinfo=UTC)
    assert "multi-agent LLM systems" in first.description_text
    assert jobs[1].remote is True


def test_ashby_feed_url():
    assert AshbyAdapter().feed_url("example-ai") == (
        "https://api.ashbyhq.com/posting-api/job-board/example-ai"
    )


def test_greenhouse_parse():
    jobs = GreenhouseAdapter().parse((FIXTURES / "greenhouse_sample.json").read_bytes())
    assert len(jobs) == 2
    first = jobs[0]
    assert first.external_id == "6123456"
    assert first.city == "Berlin"
    # first_published_at wins over updated_at; escaped HTML is decoded to text.
    assert first.posted_at == datetime(2026, 11, 11, 15, 20, tzinfo=UTC)
    assert "RAG platform" in first.description_text
    assert "&lt;" not in first.description_text
    assert jobs[1].remote is True


def test_lever_parse():
    jobs = LeverAdapter().parse((FIXTURES / "lever_sample.json").read_bytes())
    assert len(jobs) == 2
    first = jobs[0]
    assert first.title == "AI / ML Software Engineer"
    assert first.city == "Munich"
    assert first.employment_type == "Full-time"
    assert first.posted_at == datetime.fromtimestamp(1762855200000 / 1000, tz=UTC)
    assert "German B1+ welcome" in first.description_text
    intern = jobs[1]
    assert intern.employment_type == "Internship"
    assert intern.remote is True
    assert "<p>" not in intern.description_text


def test_lever_feed_url():
    assert LeverAdapter().feed_url("examplelab") == (
        "https://api.lever.co/v0/postings/examplelab?mode=json"
    )
