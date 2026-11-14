# JobRadar DE

A token-efficient job aggregator for German AI/ML roles. It replaces
job-board browsing with deterministic code: public ATS feeds are polled,
normalized, deduped and (next step) scored by rules — so an LLM only ever
reads one compact JSON of genuinely new, above-threshold postings.

Built because hosted aggregators sit behind bot walls; the employer ATS
feeds underneath them are public and happy to be read politely.

## Why it's cheap to run

- **Code-first, LLM-light** — ingestion, normalization, dedupe and scoring
  are plain Python. No browser, no LLM in the discovery path.
- **Conditional fetches** — every board is polled with its stored
  ETag / Last-Modified; an unchanged board costs one `304` response.
- **Upserts on the canonical apply URL** — one row per real posting, ever.
  Re-runs are idempotent; unchanged postings hash to zero diff.
- **Compact export** — `GET /api/export` returns only active jobs without
  descriptions. A run that found nothing new yields an empty delta.

## Sources (public feeds/APIs only)

| ATS | Feed | Status |
| --- | --- | --- |
| Personio | XML feed per company | ✅ implemented |
| Ashby | Public posting API | planned |
| Greenhouse | Public board API | planned |
| Lever | Public postings API | planned |
| Recruitee / SmartRecruiters / Workable | Public APIs | planned |

Companies are data, not code: add an entry to `data/companies.yaml`
(name, ATS, board id from the employer's own career page) and it is polled
on the next run. Only official public feeds are used, at one request per
board per run, respecting each feed's caching headers.

## Pipeline

`ingest → normalize → dedupe → score (rules, next step) → export`

Scoring will mirror a fixed rule set: AI Agentic / ML / MLOps / AI-software
roles, Germany first, German-language requirements weighted lightly
(hard-skip only above C1), full-time > internship > working student,
driving-licence requirements flagged. Above-threshold roles land in the
export with their per-factor breakdown.

## Quick start

```bash
docker compose up --build
# API on http://localhost:8000 — worker polls all enabled boards hourly
```

Or locally (SQLite, no Docker):

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Seed the registry, then trigger a run:

```bash
python -c "from app.db import SessionLocal, init_db; from app.registry import load_companies; init_db(); print(load_companies(SessionLocal(), 'data/companies.yaml'))"
curl -X POST http://localhost:8000/api/ingest/run
curl http://localhost:8000/api/export
```

## Development

```bash
pip install -e ".[dev]"
ruff check .
pytest
```

Tests run entirely on recorded fixtures — no network, no live boards.

## Status

Step 1 of the MVP: skeleton (FastAPI + PostgreSQL/SQLite + Docker + CI),
adapter contract, Personio adapter, idempotent ingest with change stats.
Next: Ashby / Greenhouse / Lever adapters, then the scoring engine,
tracker dedupe, and the dashboard.
