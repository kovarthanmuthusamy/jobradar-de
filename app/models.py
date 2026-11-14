"""Normalized storage: companies (feed registry) and jobs (one row per canonical apply URL)."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (UniqueConstraint("ats", "board_id", name="uq_company_ats_board"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    ats: Mapped[str] = mapped_column(String(50), index=True)  # personio | greenhouse | ...
    board_id: Mapped[str] = mapped_column(String(200))  # ATS-specific board token/subdomain
    feed_url_override: Mapped[str | None] = mapped_column(String(500), nullable=True)
    careers_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Conditional-fetch state: lets an unchanged feed cost one tiny 304 response.
    etag: Mapped[str | None] = mapped_column(String(300), nullable=True)
    last_modified: Mapped[str | None] = mapped_column(String(200), nullable=True)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_new: Mapped[int] = mapped_column(default=0)

    jobs: Mapped[list["Job"]] = relationship(back_populates="company")


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    source: Mapped[str] = mapped_column(String(50), index=True)  # adapter name, e.g. "personio"
    external_id: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(500))
    location_text: Mapped[str | None] = mapped_column(String(300), nullable=True)
    city: Mapped[str | None] = mapped_column(String(150), nullable=True, index=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    remote: Mapped[bool] = mapped_column(Boolean, default=False)
    employment_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Canonical apply URL is the dedupe key: one row per real posting, ever.
    apply_url: Mapped[str] = mapped_column(String(1000), unique=True, index=True)
    description_text: Mapped[str] = mapped_column(Text, default="")
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    company: Mapped[Company] = relationship(back_populates="jobs")
