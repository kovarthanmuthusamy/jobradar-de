"""Dedupe against the existing application tracker (the dashboard's data.json).

Standing rule: never re-surface a role that was already applied to or
rejected — including reposts of rejected roles. Entries with status
Submitted / Rejected / Unconfirmed suppress a match; Parked and Skipped
do not (parked roles are deliberately waiting, skipped ones never applied).

Two match layers, strongest first:
1. Apply URL — tracker notes usually record the exact portal URL used,
   which is language-independent (tracker titles are often English
   paraphrases of German feed titles, so title matching alone misses).
2. Company + fuzzy title (overlap coefficient; tracker roles often carry
   location suffixes like "AI Engineer, Berlin hybrid").
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.adapters.base import canonicalize_url

_SUPPRESSING_STATUSES = {"submitted", "rejected", "unconfirmed"}
_LEGAL_SUFFIXES = {"gmbh", "se", "ag", "kg", "kgaa", "ohg", "ug", "bv", "ltd", "inc", "co"}
_PUNCT_RE = re.compile(r"[^a-z0-9äöüß ]+")
_URL_RE = re.compile(r"https?://[^\s\"'\)\]<>]+")
# Tracker notes often carry scheme-less ATS links: "(tngtech.jobs.personio.de/job/1640429)".
_BARE_ATS_URL_RE = re.compile(
    r"(?:[a-z0-9-]+\.)*(?:personio\.de|personio\.com|ashbyhq\.com|greenhouse\.io|"
    r"lever\.co|recruitee\.com|smartrecruiters\.com|workable\.com)/[^\s\"'\)\]<>]+"
)


def _normalize(text: str) -> str:
    text = _PUNCT_RE.sub(" ", (text or "").lower())
    return " ".join(text.split())


def company_key(name: str) -> str:
    tokens = [t for t in _normalize(name).split() if t not in _LEGAL_SUFFIXES]
    return " ".join(tokens)


def title_key(title: str) -> str:
    return _normalize(title)


# Gender/diversity boilerplate tokens appear in nearly every German title
# ("(m/w/d)") and would otherwise inflate the title-overlap coefficient into
# false-positive matches between unrelated roles at the same company.
_TITLE_NOISE = {"m", "w", "d", "f", "x", "mwd", "gn", "all genders"}


def _tokens(text: str) -> set[str]:
    return {t for t in _normalize(text).split() if t not in _TITLE_NOISE}


@dataclass
class TrackerIndex:
    urls: set[str] = field(default_factory=set)
    entries: list[tuple[str, str, set[str]]] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.urls or self.entries)


def load_tracker_keys(path: str | Path) -> TrackerIndex:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items = data.get("jobs", data) if isinstance(data, dict) else data
    index = TrackerIndex()
    for item in items:
        if (item.get("status") or "").strip().lower() not in _SUPPRESSING_STATUSES:
            continue
        for value in item.values():
            if isinstance(value, str):
                found = [u for u in _URL_RE.findall(value)]
                found += [
                    f"https://{u}" for u in _BARE_ATS_URL_RE.findall(value) if "://" not in u
                ]
                for url in found:
                    index.urls.add(canonicalize_url(url.rstrip(".,;")))
        role = item.get("role") or item.get("title") or ""
        index.entries.append(
            (company_key(item.get("company") or ""), title_key(role), _tokens(role))
        )
    return index


def _company_matches(a: str, b: str) -> bool:
    if a == b:
        return True
    # Tracker names often carry extra words the registry omits, e.g. tracker
    # "octonomy AI GmbH" vs registry "octonomy" — accept a token-subset match
    # when the smaller side is distinctive enough not to over-match.
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return False
    smaller, larger = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if not smaller <= larger:
        return False
    return len(smaller) >= 2 or any(len(t) >= 4 for t in smaller)


def is_tracker_match(
    index: TrackerIndex, company: str, title: str, apply_url: str | None = None
) -> bool:
    if apply_url and canonicalize_url(apply_url) in index.urls:
        return True
    c_key = company_key(company)
    t_key = title_key(title)
    t_tokens = _tokens(title)
    for key_company, key_title, key_tokens in index.entries:
        if not _company_matches(key_company, c_key):
            continue
        if key_title == t_key:
            return True
        if key_tokens and t_tokens:
            # Overlap coefficient (vs. the smaller set): tracker roles often
            # carry location suffixes that would sink a Jaccard score.
            overlap = len(key_tokens & t_tokens) / min(len(key_tokens), len(t_tokens))
            if overlap >= 0.6:
                return True
    return False
