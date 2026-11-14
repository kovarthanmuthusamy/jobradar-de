"""Source adapters: one per ATS. Each turns a public feed into RawJob records."""

from app.adapters.ashby import AshbyAdapter
from app.adapters.base import BaseAdapter, FetchResult, RawJob
from app.adapters.greenhouse import GreenhouseAdapter
from app.adapters.lever import LeverAdapter
from app.adapters.personio import PersonioAdapter

ADAPTERS: dict[str, BaseAdapter] = {
    PersonioAdapter.name: PersonioAdapter(),
    AshbyAdapter.name: AshbyAdapter(),
    GreenhouseAdapter.name: GreenhouseAdapter(),
    LeverAdapter.name: LeverAdapter(),
    # Later, in spec order: recruitee, smartrecruiters, workable.
}

__all__ = ["ADAPTERS", "BaseAdapter", "FetchResult", "RawJob"]
