"""Rule-based scoring v1 — deterministic, explainable, no LLM.

Mirrors the standing job-search rules: target AI/ML software roles, Germany
first then NL/NO/UK/AT, entry/mid welcome, German requirements weighted a
LITTLE (B2 and below weighted lightly; C1/fluent/verhandlungssicher
hard-excluded unless English is a stated working language; native/C2
always hard-excluded), full-time > internship, working-student
roles hard-excluded (standing rule, 2026-11-17), driving-licence
requirements flagged. Every point is accounted for in the breakdown so a
human (or a later pipeline step) can see exactly why.
"""

import re
from dataclasses import dataclass, field

from app.models import Job

THRESHOLD = 50  # surfaces when total > THRESHOLD (lowered 60 -> 50 on 2026-11-17)

_ROLE_PATTERNS: list[tuple[str, int]] = [
    (r"machine learning engineer", 38),
    (r"\bml engineer\b", 38),
    (r"\bmlops\b", 38),
    (r"agentic", 38),
    (r"\bai engineer", 38),
    (r"deep learning", 36),
    (r"applied ai", 36),
    (r"ai software", 36),
    (r"\bllm\b", 36),
    (r"computer vision", 34),
    (r"\bnlp\b", 34),
    (r"forward deployed", 33),
    (r"maschinelles lernen", 36),
    (r"künstliche intelligenz", 34),
    (r"research engineer", 26),
    (r"data scien", 26),
    (r"datenwissenschaft", 24),
    (r"softwareentwickl", 22),
    (r"robotik", 22),
    (r"\bki\b", 18),
    (r"software engineer", 20),
    (r"software developer", 20),
    (r"data engineer", 16),
    (r"developer", 12),
    (r"engineer", 10),
]

_STACK_KEYWORDS = [
    "python", "pytorch", "tensorflow", "llm", "rag", "langchain", "langgraph",
    "agent", "fastapi", "docker", "kubernetes", "mlflow", "airflow", "spark",
    "kafka", "vector", "embedding", "transformers", "fine-tuning", "sql",
    "terraform", "ci/cd", "aws", "azure", "gcp",
]

_DE_CITIES = {
    "berlin", "munich", "münchen", "hamburg", "cologne", "köln", "frankfurt",
    "stuttgart", "dortmund", "düsseldorf", "leipzig", "dresden", "nuremberg",
    "nürnberg", "hannover", "bremen", "freiburg", "heidelberg", "aachen",
    "bonn", "essen", "bochum", "karlsruhe", "mannheim", "augsburg", "wiesbaden",
    "münster", "bielefeld", "wuppertal", "rostock", "mainz", "kassel", "halle",
    "magdeburg", "kiel", "erfurt", "regensburg", "ingolstadt", "ulm", "potsdam",
    "jena", "tübingen", "göttingen", "wolfsburg", "heilbronn", "paderborn",
}
_OTHER_CITIES = {
    "amsterdam": "Netherlands", "eindhoven": "Netherlands", "utrecht": "Netherlands",
    "rotterdam": "Netherlands", "oslo": "Norway", "bergen": "Norway",
    "trondheim": "Norway", "london": "UK", "cambridge": "UK", "edinburgh": "UK",
    "manchester": "UK", "vienna": "Austria", "wien": "Austria", "graz": "Austria",
    "linz": "Austria",
}
_TARGET_COUNTRIES = {"Germany", "Netherlands", "Norway", "UK", "Austria"}
# Known non-target cities: when a posting's own location names one of these,
# it must NOT inherit the company's (German) HQ country as a fallback.
_FOREIGN_CITIES = {
    "budapest", "sofia", "sevilla", "seville", "melbourne", "sydney", "paris",
    "warsaw", "prague", "bucharest", "zurich", "zürich", "geneva", "genf",
    "stockholm", "copenhagen", "helsinki", "dublin", "madrid", "barcelona",
    "lisbon", "milan", "rome", "brussels", "luxembourg", "new york",
    "san francisco", "toronto", "singapore", "tokyo", "bangalore", "tel aviv",
    # Seen on global Ashby/Greenhouse boards during the first full run:
    "são paulo", "sao paulo", "palo alto", "montréal", "montreal", "austin",
    "boston", "seattle", "chicago", "vancouver", "hyderabad", "canada",
    "brazil", "usa", "united states", "india", "australia", "switzerland",
    "schweiz", "sweden", "spain", "france", "italy", "poland", "hungary",
    # Seen in batch 2 (Awin board): Romanian office surfacing as in-scope.
    "iași", "iasi", "romania", "rumänien",
}

_GERMAN_LEVEL_RE = re.compile(
    r"(deutsch|german)[^.\n]{0,60}?\b(a1|a2|b1|b2|c1|c2)\b|\b(a1|a2|b1|b2|c1|c2)\b[^.\n]{0,60}?(deutsch|german)",
    re.IGNORECASE,
)
_GERMAN_ABOVE_C1_RE = re.compile(
    r"muttersprach|native (speaker|german)|"
    r"\bc2\b[^.\n]{0,40}(deutsch|german)|(deutsch|german)[^.\n]{0,40}\bc2\b",
    re.IGNORECASE,
)
# C1-tier German (fluent / fließend): hard-excluded since 2026-11-17 unless
# the posting states English as a working language. B2 and below stay allowed.
_GERMAN_FLUENT_RE = re.compile(
    r"fließend\w*\s+deutsch|deutsch[^.\n]{0,40}fließend|"
    r"fließende[rsn]?\s+deutschkenntnisse|deutschkenntnisse[^.\n]{0,30}fließend|"
    r"fluent\w*\s+(in\s+)?german|german[^.\n]{0,40}fluent",
    re.IGNORECASE,
)
_ENGLISH_WORKING_RE = re.compile(
    r"working language[^.\n]{0,40}english|english[^.\n]{0,40}working language|"
    r"company language[^.\n]{0,40}english|corporate language[^.\n]{0,40}english|"
    r"arbeitssprache[^.\n]{0,40}englisch|englisch[^.\n]{0,40}arbeitssprache|"
    r"unternehmenssprache[^.\n]{0,40}englisch|"
    r"english-speaking (team|environment|workplace|office|company)",
    re.IGNORECASE,
)


def _german_fluent_hit(text: str) -> re.Match | None:
    """A C1-tier German requirement: a fluent pattern, or 'verhandlungssicher'
    in a German context. The same word tied to Englisch/English does NOT
    count — English at any level is acceptable."""
    match = _GERMAN_FLUENT_RE.search(text)
    if match:
        return match
    for m in re.finditer(r"verhandlungssicher", text, re.IGNORECASE):
        before = text[max(0, m.start() - 45) : m.start()]
        if re.search(r"deutsch|german", before, re.IGNORECASE) or not re.search(
            r"englisch|english", before, re.IGNORECASE
        ):
            return m
    return None
_GERMAN_PLUS_RE = re.compile(
    r"(plus|von vorteil|nice to have|a bonus|wünschenswert)", re.IGNORECASE
)
_DRIVING_RE = re.compile(
    r"führerschein|fahrerlaubnis|driving licen[cs]e|driver'?s licen[cs]e", re.IGNORECASE
)
# Talent-pool / speculative postings are not concrete roles — the pipeline
# never applies to them as if they were, so they must not surface.
_TALENT_POOL_RE = re.compile(
    r"talent pool|talentpool|talent community|express interest|general application|"
    r"initiativbewerbung|unsolicited application|speculative application",
    re.IGNORECASE,
)
_YEARS_RE = re.compile(r"(\d+)\s*\+?\s*(years?|jahre)\b", re.IGNORECASE)
# Working-student roles are excluded entirely (standing rule, 2026-11-17).
# Detection is deliberately scoped to the title and the employment type —
# NOT the description, which mentions working students in passing for
# unrelated roles. Internships are NOT caught by this (they stay allowed).
_WS_TITLE_RE = re.compile(r"werkstudent|working[\s-]?student", re.IGNORECASE)


def _is_working_student(job: Job) -> bool:
    if _WS_TITLE_RE.search(job.title or ""):
        return True
    et = (job.employment_type or "").lower().replace("_", " ")
    return "working student" in et or "werkstudent" in et


@dataclass
class ScoreResult:
    total: int
    breakdown: dict[str, int]
    flags: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def surfaces(self) -> bool:
        return self.total > THRESHOLD and not self.flags


def resolve_country(job: Job) -> str | None:
    """Location evidence from the posting itself beats the stored country
    (which may just be the company's HQ country, stamped at ingest)."""
    text = f"{job.location_text or ''} {job.city or ''}".lower()
    city = (job.city or "").strip().lower()
    if "germany" in text or "deutschland" in text:
        return "Germany"
    if city in _DE_CITIES or any(c in text for c in _DE_CITIES):
        return "Germany"
    if city in _OTHER_CITIES:
        return _OTHER_CITIES[city]
    for name, country in _OTHER_CITIES.items():
        if name in text:
            return country
    if city in _FOREIGN_CITIES or any(c in text for c in _FOREIGN_CITIES):
        return city.title() or "Outside target area"
    if job.country:
        return job.country
    return None


def _role_score(title: str, text: str) -> tuple[int, list[str]]:
    notes: list[str] = []
    base = 5
    for pattern, points in _ROLE_PATTERNS:
        if re.search(pattern, title):
            base = points
            notes.append(f"title match '{pattern}' = {points}")
            break
    stack_hits = [kw for kw in _STACK_KEYWORDS if kw in text]
    stack_points = min(10, 2 * len(stack_hits))
    if base == 20 and len(stack_hits) >= 3:
        base = 30
        notes.append("generic dev title but strong ML stack in text -> base 30")
    if stack_points:
        notes.append(f"stack hits {stack_hits[:6]} +{stack_points}")
    return min(45, base + stack_points), notes


def _location_score(job: Job) -> tuple[int, str | None, list[str]]:
    country = resolve_country(job)
    if country == "Germany":
        return 20, country, []
    if country in _TARGET_COUNTRIES:
        return 14, country, []
    if job.remote and country is None:
        return 8, country, []
    if country is None:
        return 6, country, []
    return 0, country, ["outside_target_locations"]


def _seniority_score(title: str, text: str) -> int:
    score = 10
    if re.search(r"junior|entry|graduate|absolvent|berufseinsteiger", title):
        score = 15
    elif re.search(r"working student|werkstudent|intern|praktik", title):
        score = 13
    elif re.search(r"\bsenior\b", title):
        score = 4
    elif re.search(r"staff|principal", title):
        score = 2
    elif re.search(r"\blead\b|head of", title):
        score = 5
    years = [int(m.group(1)) for m in _YEARS_RE.finditer(text)]
    if years:
        required = min(years)
        if required >= 5:
            score = min(score, 3)
        elif required >= 3:
            score = min(score, 7)
        elif required >= 1:
            score = max(score, 12) if score >= 10 else score
    return score


def _german_score(text: str) -> tuple[int, list[str], list[str]]:
    notes: list[str] = []
    if _GERMAN_ABOVE_C1_RE.search(text):
        return 0, ["german_above_c1"], ["German above C1 (native/C2) — hard skip"]
    match = _GERMAN_LEVEL_RE.search(text)
    level = None
    if match:
        level = next(g for g in match.groups() if g and len(g) == 2).lower()
    fluent = _german_fluent_hit(text)
    if fluent is not None or level == "c1":
        # C1-tier German requirement (C1 / fluent / verhandlungssicher):
        # hard exclude since 2026-11-17, unless English is a stated
        # working language or the German is only a plus.
        anchor = fluent if fluent is not None else match
        window = text[max(0, anchor.start() - 80) : anchor.end() + 80]
        if _GERMAN_PLUS_RE.search(window):
            return 9, [], ["German C1/fluent stated as a plus, not a requirement"]
        if _ENGLISH_WORKING_RE.search(text):
            return 8, [], [
                "German C1/fluent required, but English is a stated working "
                "language — allowed (rule 2026-11-17)"
            ]
        return 0, ["german_c1_required"], [
            "German C1/fluent/verhandlungssicher required — hard exclude (rule 2026-11-17)"
        ]
    if match:
        window = text[max(0, match.start() - 80) : match.end() + 80]
        if _GERMAN_PLUS_RE.search(window):
            return 9, [], [f"German {level.upper()} stated as a plus"]
        points = {"a1": 10, "a2": 10, "b1": 9, "b2": 8, "c2": 0}[level]
        notes.append(f"German {level.upper()} required -> {points}/10 (small weight, per rule)")
        if level == "c2":
            return 0, ["german_above_c1"], notes
        return points, [], notes
    if re.search(r"\bdeutsch|\bgerman\b", text, re.IGNORECASE):
        return 7, [], ["German mentioned without a level"]
    return 10, [], []


def _type_score(job: Job) -> int:
    text = f"{job.employment_type or ''} {job.title}".lower()
    if "full" in text or "permanent" in text or "vollzeit" in text:
        return 10
    if "part" in text or "working student" in text or "werkstudent" in text or "teilzeit" in text:
        return 5
    if "intern" in text or "praktik" in text:
        return 7
    return 6


def score_job(job: Job) -> ScoreResult:
    title = job.title.lower()
    text = f"{job.title}\n{job.description_text or ''}".lower()
    flags: list[str] = []
    notes: list[str] = []

    role, role_notes = _role_score(title, text)
    notes += role_notes
    location, _country, location_flags = _location_score(job)
    flags += location_flags
    seniority = _seniority_score(title, text)
    german, german_flags, german_notes = _german_score(text)
    flags += german_flags
    notes += german_notes
    if _DRIVING_RE.search(text):
        flags.append("driving_licence_required")
        notes.append("Driving licence required — hard flag (he has none)")
    if _TALENT_POOL_RE.search(job.title):
        flags.append("talent_pool")
        notes.append("Talent-pool/speculative posting, not a concrete role")
    if _is_working_student(job):
        flags.append("working_student_excluded")
        notes.append(
            "Working-student role — hard flag (excluded entirely by standing rule, 2026-11-17)"
        )
    type_points = _type_score(job)

    breakdown = {
        "role": role,
        "location": location,
        "seniority": seniority,
        "german": german,
        "type": type_points,
    }
    return ScoreResult(
        total=sum(breakdown.values()), breakdown=breakdown, flags=flags, notes=notes
    )
