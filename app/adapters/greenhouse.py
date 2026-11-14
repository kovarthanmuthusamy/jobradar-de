"""Greenhouse adapter — official public Job Board API.

Feed: https://boards-api.greenhouse.io/v1/boards/<board_token>/jobs?content=true
Returns {"jobs": [...]}; `content` is entity-escaped HTML, `absolute_url` the job page.
"""

import html
import json
from datetime import UTC, datetime

from app.adapters.base import BaseAdapter, RawJob, canonicalize_url, html_to_text


def _parse_iso(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return None


class GreenhouseAdapter(BaseAdapter):
    name = "greenhouse"

    def feed_url(self, board_id: str, override: str | None = None) -> str:
        return override or f"https://boards-api.greenhouse.io/v1/boards/{board_id}/jobs?content=true"

    def parse(self, content: bytes) -> list[RawJob]:
        data = json.loads(content)
        jobs: list[RawJob] = []
        for item in data.get("jobs", []):
            ext_id = str(item.get("id") or "")
            title = (item.get("title") or "").strip()
            apply_url = item.get("absolute_url") or ""
            if not ext_id or not title or not apply_url:
                continue
            location = ((item.get("location") or {}).get("name") or "").strip()
            description = html_to_text(html.unescape(item.get("content") or ""))
            jobs.append(
                RawJob(
                    external_id=ext_id,
                    title=title,
                    apply_url=canonicalize_url(apply_url),
                    location_text=location or None,
                    city=location.split(",")[0].strip() or None,
                    remote="remote" in location.lower(),
                    employment_type=None,
                    description_text=description,
                    posted_at=_parse_iso(item.get("first_published_at") or item.get("updated_at")),
                )
            )
        return jobs
