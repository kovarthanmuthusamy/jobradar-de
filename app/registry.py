"""Seed/refresh the company registry from a YAML file (data/companies.yaml).

Adding a company is a data change, never a code change: name, ATS, board id.
"""

from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from app.models import Company


def load_companies(db: Session, path: str | Path) -> int:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    count = 0
    for entry in data.get("companies", []):
        existing = (
            db.query(Company)
            .filter(Company.ats == entry["ats"], Company.board_id == entry["board_id"])
            .one_or_none()
        )
        if existing is None:
            db.add(
                Company(
                    name=entry["name"],
                    ats=entry["ats"],
                    board_id=entry["board_id"],
                    feed_url_override=entry.get("feed_url"),
                    careers_url=entry.get("careers_url"),
                    country=entry.get("country"),
                    size_band=entry.get("size_band"),
                    enabled=entry.get("enabled", True),
                )
            )
            count += 1
        else:
            existing.name = entry["name"]
            existing.careers_url = entry.get("careers_url", existing.careers_url)
            existing.country = entry.get("country", existing.country)
            existing.size_band = entry.get("size_band", existing.size_band)
            existing.enabled = entry.get("enabled", existing.enabled)
    db.commit()
    return count
