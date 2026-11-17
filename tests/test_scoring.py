from app.models import Job
from app.scoring import score_job


def _job(**kwargs) -> Job:
    defaults = {
        "company_id": 1,
        "source": "personio",
        "external_id": "1",
        "title": "Machine Learning Engineer",
        "location_text": "Berlin",
        "city": "Berlin",
        "country": "Germany",
        "remote": False,
        "employment_type": "full-time permanent",
        "apply_url": "https://example.jobs.personio.de/job/1",
        "description_text": "Python, PyTorch, FastAPI, Docker, Kubernetes, LLM and RAG.",
        "content_hash": "x",
    }
    defaults.update(kwargs)
    return Job(**defaults)


def test_strong_ml_role_in_berlin_surfaces():
    result = score_job(_job())
    assert result.total > 90
    assert result.surfaces is True
    assert result.breakdown["location"] == 20
    assert result.breakdown["type"] == 10


def test_german_b2_as_plus_costs_almost_nothing():
    result = score_job(_job(description_text="Python and Docker. German B2 is a plus."))
    assert result.breakdown["german"] == 9
    assert result.surfaces is True


def test_german_c1_required_is_only_a_small_deduction():
    result = score_job(
        _job(
            description_text="Python, Docker, Kubernetes. "
            "Deutschkenntnisse auf C1-Niveau erforderlich."
        )
    )
    assert result.breakdown["german"] == 5
    assert "german_above_c1" not in result.flags


def test_german_native_level_is_a_hard_skip():
    result = score_job(_job(description_text="Python. Deutsch auf muttersprachlichem Niveau."))
    assert "german_above_c1" in result.flags
    assert result.surfaces is False


def test_driving_licence_is_a_hard_flag():
    result = score_job(_job(description_text="Python. Führerschein Klasse B erforderlich."))
    assert "driving_licence_required" in result.flags
    assert result.surfaces is False


def test_senior_role_with_5_years_is_penalized():
    result = score_job(
        _job(
            title="Senior Machine Learning Engineer",
            description_text="Python. 5+ years of experience.",
        )
    )
    assert result.breakdown["seniority"] <= 4


def test_outside_target_location_scores_zero_and_flags():
    result = score_job(_job(city="New York", location_text="New York", country="USA"))
    assert result.breakdown["location"] == 0
    assert "outside_target_locations" in result.flags
    assert result.surfaces is False


def test_foreign_office_does_not_inherit_company_country():
    # Company HQ country is Germany, but the posting itself is Budapest.
    result = score_job(
        _job(title="Software Developer / Consultant", city="Budapest", location_text="Budapest")
    )
    assert result.breakdown["location"] == 0
    assert "outside_target_locations" in result.flags
    assert result.surfaces is False


def test_sao_paulo_office_does_not_surface():
    result = score_job(
        _job(
            title="Forward Deployed Engineer",
            city="São Paulo Office",
            location_text="São Paulo Office",
            country=None,
        )
    )
    assert result.breakdown["location"] == 0
    assert result.surfaces is False


def test_talent_pool_posting_is_flagged():
    result = score_job(_job(title="Computer Vision Engineering - Talent Pool"))
    assert "talent_pool" in result.flags
    assert result.surfaces is False


def test_werkstudent_title_is_hard_flagged():
    result = score_job(_job(title="Werkstudent KI & Robotik (m/w/d)"))
    assert "working_student_excluded" in result.flags
    assert result.surfaces is False


def test_working_student_employment_type_is_hard_flagged():
    result = score_job(
        _job(title="Data Analyst", employment_type="part-time working_student")
    )
    assert "working_student_excluded" in result.flags
    assert result.surfaces is False


def test_internship_is_not_caught_by_working_student_rule():
    result = score_job(
        _job(title="Machine Learning Intern", employment_type="full-time intern")
    )
    assert "working_student_excluded" not in result.flags


def test_german_title_patterns_match():
    result = score_job(
        _job(
            title="Praktikum im Bereich Robotik und KI (m/w/d)",
            city="Munich",
            location_text="Munich",
            employment_type="full-time intern",
            description_text="Python, Robotik, Sensorik und Bildverarbeitung.",
        )
    )
    assert result.breakdown["role"] >= 22


def test_other_target_country_scores_partially():
    result = score_job(_job(city="Amsterdam", location_text="Amsterdam", country="Netherlands"))
    assert result.breakdown["location"] == 14


def test_working_student_type_scores_lowest_but_can_surface():
    result = score_job(
        _job(
            title="Working Student Data Science",
            city="Munich",
            location_text="Munich",
            employment_type="part-time intern",
            description_text="Python and SQL dashboards.",
        )
    )
    assert result.breakdown["type"] == 5
    assert result.breakdown["role"] < 40
