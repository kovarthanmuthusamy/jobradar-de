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
| Ashby | Public posting API | ✅ implemented |
| Greenhouse | Public board API | ✅ implemented |
| Lever | Public postings API | ✅ implemented |
| Recruitee / SmartRecruiters / Workable | Public APIs | planned |

Companies are data, not code: add an entry to `data/companies.yaml`
(name, ATS, board id from the employer's own career page) and it is polled
on the next run. Only official public feeds are used, at one request per
board per run, respecting each feed's caching headers.

## Pipeline

`ingest → normalize → dedupe → score (rules) → export`

Scoring mirrors a fixed rule set: AI Agentic / ML / MLOps / AI-software
roles, Germany first (then NL/NO/UK/AT), German-language requirements
weighted lightly at B2 and below (C1/fluent/verhandlungssicher is a hard
exclude since 2026-11-17, unless the posting states English as a working
language; native/C2 is always excluded), full-time > internship,
working-student roles hard-excluded, driving-licence requirements
hard-flagged. The export also dedupes against the application tracker
(set `JOBRADAR_TRACKER_PATH` to its `data.json`): already-applied or
rejected roles never resurface. Above-threshold roles (>50) land in
`GET /api/export` with their per-factor breakdown and, where the
registry carries one, the company's approximate size band
(`company_size_band`); `?since=<ISO>` returns only a delta of new finds.

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

MVP progress: skeleton (FastAPI + PostgreSQL/SQLite + Docker + CI),
adapter contract, idempotent ingest with change stats, the four
highest-value adapters (Personio, Ashby, Greenhouse, Lever), the
rule-based scoring engine, tracker dedupe, a registry of 85 verified
company boards (72 enabled across the four adapters, 13 parked until
their adapters land), and the dashboard — 43 tests, plus live
validation: a full-registry run ingested 1,837 active postings (231
scored above the surfacing threshold after tracker dedupe), and a
repeat poll against a real Personio feed answered 304 Not Modified,
as designed. Next: Recruitee / SmartRecruiters / Workable adapters,
and feeding the export to the job-search pipeline's scheduled runs.
