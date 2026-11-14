"""Ashby adapter — official public posting API.

Feed: https://api.ashbyhq.com/posting-api/job-board/<board_name>
Returns {"jobs": [...]} with hosted jobUrl/applyUrl and ISO publishedAt.
"""

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


class AshbyAdapter(BaseAdapter):
    name = "ashby"

    def feed_url(self, board_id: str, override: str | None = None) -> str:
        return override or f"https://api.ashbyhq.com/posting-api/job-board/{board_id}"

    def parse(self, content: bytes) -> list[RawJob]:
        data = json.loads(content)
        jobs: list[RawJob] = []
        for item in data.get("jobs", []):
            ext_id = str(item.get("id") or "")
            title = (item.get("title") or "").strip()
            apply_url = item.get("applyUrl") or item.get("jobUrl") or ""
            if not ext_id or not title or not apply_url:
                continue
            location = item.get("locationName") or item.get("location") or ""
            workplace = (item.get("workplaceType") or "").lower()
            jobs.append(
                RawJob(
                    external_id=ext_id,
                    title=title,
                    apply_url=canonicalize_url(apply_url),
                    location_text=location or None,
                    city=location.split(",")[0].strip() or None,
                    remote=workplace == "remote" or "remote" in location.lower(),
                    employment_type=item.get("employmentType"),
                    description_text=html_to_text(item.get("descriptionHtml") or ""),
                    posted_at=_parse_iso(item.get("publishedAt")),
                )
            )
        return jobs
