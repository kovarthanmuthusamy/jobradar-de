import json

from app.tracker import is_tracker_match, load_tracker_keys

TRACKER = {
    "jobs": [
        {"company": "Acme GmbH", "role": "AI Engineer, Berlin hybrid", "status": "Submitted"},
        {"company": "Beta SE", "role": "MLOps Engineer", "status": "Rejected"},
        {"company": "Gamma GmbH", "role": "Data Scientist", "status": "Parked"},
        {"company": "Delta", "role": "ML Engineer", "status": "Skipped"},
        {
            "company": "TNG Technology Consulting GmbH",
            "role": "Internship in Robotics and AI (m/f/d), Karlsruhe (internship, full-time)",
            "status": "Submitted",
            "notes": "SUBMITTED via TNG's Personio portal (tngtech.jobs.personio.de/job/1640429)",
        },
    ]
}


def _keys(tmp_path):
    path = tmp_path / "data.json"
    path.write_text(json.dumps(TRACKER), encoding="utf-8")
    return load_tracker_keys(path)


def test_only_suppressing_statuses_are_loaded(tmp_path):
    keys = _keys(tmp_path)
    assert len(keys.entries) == 3  # Submitted x2 + Rejected; Parked/Skipped excluded
    assert "https://tngtech.jobs.personio.de/job/1640429" in keys.urls


def test_apply_url_match_is_language_independent(tmp_path):
    keys = _keys(tmp_path)
    # German feed title vs English tracker title: only the URL connects them.
    assert (
        is_tracker_match(
            keys,
            "TNG Technology Consulting",
            "Praktikum im Bereich Robotik und KI (m/w/d)",
            "https://tngtech.jobs.personio.de/job/1640429",
        )
        is True
    )


def test_match_despite_legal_suffix_and_location_words(tmp_path):
    keys = _keys(tmp_path)
    assert is_tracker_match(keys, "Acme", "AI Engineer") is True
    assert is_tracker_match(keys, "Beta", "MLOps Engineer") is True


def test_no_match_for_other_company_or_role(tmp_path):
    keys = _keys(tmp_path)
    assert is_tracker_match(keys, "Acme", "Product Manager") is False
    assert is_tracker_match(keys, "Other Co", "AI Engineer") is False
    assert is_tracker_match(keys, "Gamma", "Data Scientist") is False  # Parked doesn't suppress
