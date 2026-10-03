import pytest

from core.db.crud import evaluations as evaluations_crud
from core.db.crud import jobs as jobs_crud
from core.db.crud import resumes as resumes_crud
from core.evaluator.persist import store_evaluation
from core.evaluator.pipeline import empty_quick_result


@pytest.mark.evaluator
def test_store_evaluation_saves_triggered_blockers(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="text")
    resume = resumes_crud.create_resume_version(db_session, source_type="resume", raw_text="resume")
    blockers = [{"number": 5, "name": "Office required", "text": "Rule five", "quote": "Hybrid"}]
    result = {
        "verdict": False,
        "score": 6,
        "cons": [],
        "pros": [],
        "matched_factors": [],
        "triggered_blockers": blockers,
    }

    evaluation = store_evaluation(db_session, job.id, resume.id, empty_quick_result(), result)

    stored = evaluations_crud.get_evaluation(db_session, evaluation.id)
    assert stored.fit_score == 6
    assert stored.triggered_blockers == blockers


@pytest.mark.evaluator
def test_store_evaluation_defaults_to_empty_blockers(db_session):
    job = jobs_crud.create_job_posting(db_session, raw_text="text")
    resume = resumes_crud.create_resume_version(db_session, source_type="resume", raw_text="resume")
    result = {"verdict": True, "score": 8, "cons": [], "pros": [], "matched_factors": []}

    evaluation = store_evaluation(db_session, job.id, resume.id, empty_quick_result(), result)

    assert evaluation.triggered_blockers == []