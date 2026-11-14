"""Personio adapter — the public XML job feed every Personio career site exposes.

Feed: https://<board>.jobs.personio.de/xml  (root <workzag-jobs>, one <position> per job).
Personio carries no per-job apply URL in the feed; the canonical public job page is
https://<board>.jobs.personio.de/job/<id>, which is what we store and dedupe on.
"""

import xml.etree.ElementTree as ET
from datetime import UTC, datetime

from app.adapters.base import BaseAdapter, RawJob, canonicalize_url, html_to_text


def _text(node: ET.Element | None, tag: str) -> str:
    if node is None:
        return ""
    child = node.find(tag)
    return (child.text or "").strip() if child is not None and child.text else ""


def _parse_created_at(raw: str) -> datetime | None:
    raw = raw.strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(raw)
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except ValueError:
        return None


class PersonioAdapter(BaseAdapter):
    name = "personio"

    def feed_url(self, board_id: str, override: str | None = None) -> str:
        return override or f"https://{board_id}.jobs.personio.de/xml"

    def parse(self, content: bytes) -> list[RawJob]:
        root = ET.fromstring(content)
        jobs: list[RawJob] = []
        for pos in root.iter("position"):
            ext_id = _text(pos, "id")
            title = _text(pos, "name")
            if not ext_id or not title:
                continue
            office = _text(pos, "office")
            additional = [
                (o.text or "").strip()
                for o in pos.findall("./additionalOffices/office")
                if o.text and o.text.strip()
            ]
            locations = [loc for loc in [office, *additional] if loc]
            schedule = _text(pos, "schedule")
            contract = _text(pos, "employmentType")
            employment = " ".join(p for p in [schedule, contract] if p) or None
            descriptions = []
            for desc in pos.findall("./jobDescriptions/jobDescription"):
                value = _text(desc, "value")
                if value:
                    descriptions.append(html_to_text(value))
            jobs.append(
                RawJob(
                    external_id=ext_id,
                    title=title,
                    apply_url="",  # stamped by parse_board, which knows the board id
                    location_text=", ".join(locations) or None,
                    city=office or None,
                    remote="remote" in " ".join(locations).lower(),
                    employment_type=employment,
                    description_text="\n\n".join(descriptions),
                    posted_at=_parse_created_at(_text(pos, "createdAt")),
                )
            )
        return jobs

    def parse_board(
        self, content: bytes, board_id: str, override: str | None = None
    ) -> list[RawJob]:
        # Boards live on personio.de or personio.com; the apply pages sit on
        # the same host as the feed, so derive the base from the feed URL.
        feed = self.feed_url(board_id, override)
        base = feed[: -len("/xml")] if feed.endswith("/xml") else feed
        jobs = self.parse(content)
        for job in jobs:
            job.apply_url = canonicalize_url(f"{base}/job/{job.external_id}")
        return jobs
