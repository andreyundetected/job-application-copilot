import pytest

from core.db.crud import evaluations as evaluations_crud
from core.db.crud import jobs as jobs_crud
from core.db.crud import resumes as resumes_crud
from core.evaluator.persist import apply_quick_meta, build_checked_keywords, store_evaluation
from core.evaluator.pipeline import empty_quick_result

_QUICK = {
    "company": "Acme",
    "role": "AI Engineer",
    "location": "Germany, Berlin",
    "location_country": "Germany",
    "location_state": None,
    "location_city": "Berlin",
    "work_mode": "remote",
    "employment_type": "full_time",
    "tags": ["Python"],
    "salary": {"min": 1.0, "max": 2.0, "currency": "USD", "period": "year", "is_estimate": False, "original_text": "x"},
    "summary": "Short summary.",
}

_RESULT = {
    "verdict": True,
    "score": 8,
    "cons": ["A con"],
    "pros": ["A pro"],
    "matched_factors": [{"id": 1, "text": "f", "direction": "plus", "weight": 1, "note": "n"}],
}


@pytest.mark.evaluator
def test_build_checked_keywords_merges_quick_and_result():
    checked = build_checked_keywords(_QUICK, _RESULT)

    assert checked["location"] == "Germany, Berlin"
    assert checked["work_mode"] == "remote"
    assert checked["salary"]["currency"] == "USD"
    assert checked["summary"] == "Short summary."
    assert checked["matched_factors"] == _RESULT["matched_factors"]


@pytest.mark.evaluator
def test_apply_quick_meta_updates_job(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="text")

    apply_quick_meta(db_session, job.id, _QUICK)

    refreshed = jobs_crud.get_job_posting(db_session, job.id)
    assert refreshed.company == "Acme"
    assert refreshed.title == "AI Engineer"
    assert refreshed.location_country == "Germany"
    assert refreshed.employment_type == "full_time"
    assert refreshed.tags == ["Python"]


@pytest.mark.evaluator
def test_store_evaluation_saves_scores_and_metadata(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="text")
    resume = resumes_crud.create_resume_version(db_session, source_type="resume", raw_text="resume")

    evaluation = store_evaluation(db_session, job.id, resume.id, _QUICK, _RESULT)

    stored = evaluations_crud.get_evaluation(db_session, evaluation.id)
    assert stored.fit_score == 8
    assert stored.verdict is True
    assert stored.fit_bullets == {"pros": ["A pro"]}
    assert stored.blocker_bullets == {"cons": ["A con"]}
    assert stored.checked_keywords["summary"] == "Short summary."


@pytest.mark.evaluator
def test_store_evaluation_works_with_empty_quick_result(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="text")
    resume = resumes_crud.create_resume_version(db_session, source_type="resume", raw_text="resume")

    evaluation = store_evaluation(db_session, job.id, resume.id, empty_quick_result(), _RESULT)

    assert evaluation.fit_score == 8
    assert evaluation.checked_keywords["salary"]["min"] is None
    assert evaluation.checked_keywords["summary"] is None