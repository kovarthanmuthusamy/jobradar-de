"""Lever adapter — official public Postings API.

Feed: https://api.lever.co/v0/postings/<site>?mode=json
Returns a bare list of postings; createdAt is epoch milliseconds.
"""

import json
from datetime import UTC, datetime

from app.adapters.base import BaseAdapter, RawJob, canonicalize_url, html_to_text


class LeverAdapter(BaseAdapter):
    name = "lever"

    def feed_url(self, board_id: str, override: str | None = None) -> str:
        return override or f"https://api.lever.co/v0/postings/{board_id}?mode=json"

    def parse(self, content: bytes) -> list[RawJob]:
        data = json.loads(content)
        jobs: list[RawJob] = []
        for item in data if isinstance(data, list) else []:
            ext_id = str(item.get("id") or "")
            title = (item.get("text") or "").strip()
            apply_url = item.get("applyUrl") or item.get("hostedUrl") or ""
            if not ext_id or not title or not apply_url:
                continue
            categories = item.get("categories") or {}
            location = (categories.get("location") or "").strip()
            created_ms = item.get("createdAt")
            posted = (
                datetime.fromtimestamp(created_ms / 1000, tz=UTC)
                if isinstance(created_ms, (int, float))
                else None
            )
            description = item.get("descriptionPlain") or html_to_text(
                item.get("description") or ""
            )
            jobs.append(
                RawJob(
                    external_id=ext_id,
                    title=title,
                    apply_url=canonicalize_url(apply_url),
                    location_text=location or None,
                    city=location.split(",")[0].strip() or None,
                    remote="remote" in location.lower()
                    or (item.get("workplaceType") or "").lower() == "remote",
                    employment_type=categories.get("commitment"),
                    description_text=description.strip(),
                    posted_at=posted,
                )
            )
        return jobs
