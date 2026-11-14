"""Runtime configuration from environment variables (no config files, no secrets)."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.environ.get("DATABASE_URL", "sqlite:///./jobradar.db")
    ingest_interval_seconds: int = int(os.environ.get("INGEST_INTERVAL_SECONDS", "3600"))
    ingest_user_agent: str = os.environ.get(
        "INGEST_USER_AGENT", "JobRadarDE/0.1 (+personal job aggregator)"
    )
    http_timeout_seconds: float = float(os.environ.get("HTTP_TIMEOUT_SECONDS", "30"))


settings = Settings()
