import pytest

from core.db.models import (
    Application,
    BlockerRule,
    Evaluation,
    FormQuestion,
    JobPosting,
    ResumeVersion,
    ScoringFactor,
    TailoredResume,
    TaskStatus,
)


@pytest.mark.db
def test_create_job_posting(db_session):
    job = JobPosting(raw_text="some job text", company="Acme", title="Backend Dev")
    db_session.add(job)
    db_session.commit()

    fetched = db_session.query(JobPosting).first()
    assert fetched.raw_text == "some job text"
    assert fetched.company == "Acme"
    assert fetched.archived is False


@pytest.mark.db
def test_evaluation_relationships(db_session):
    resume = ResumeVersion(source_type="resume", raw_text="resume text")
    job = JobPosting(raw_text="job text")
    db_session.add_all([resume, job])
    db_session.commit()

    evaluation = Evaluation(
        job_posting_id=job.id,
        resume_version_id=resume.id,
        verdict=True,
        blocker_bullets={"passed": ["years_ok", "stack_ok"]},
        fit_score=8,
        fit_bullets={"positives": ["strong stack match"]},
        checked_keywords={"years_of_experience": True},
    )
    # placeholder data only, no personal info
    db_session.add(evaluation)
    db_session.commit()

    assert evaluation.job_posting.id == job.id
    assert evaluation.resume_version.id == resume.id
    assert job.evaluations[0].id == evaluation.id


@pytest.mark.db
def test_tailored_resume_flexible_content(db_session):
    resume = ResumeVersion(source_type="linkedin", raw_text="linkedin text")
    job = JobPosting(raw_text="job text")
    db_session.add_all([resume, job])
    db_session.commit()

    evaluation = Evaluation(
        job_posting_id=job.id,
        resume_version_id=resume.id,
        verdict=True,
    )
    db_session.add(evaluation)
    db_session.commit()

    content_blocks = [
        {"type": "summary", "text": "Experienced software engineer."},
        {
            "type": "experience",
            "role": "Software Engineer",
            "company": "Example Corp",
            "dates": "2024-2026",
            "bullets": ["Built internal tooling", "Led a small feature team"],
        },
        {"type": "skills", "items": ["Python", "SQL", "FastAPI"]},
    ]

    tailored = TailoredResume(
        evaluation_id=evaluation.id,
        keywords_used={"stack": ["Python", "FastAPI"]},
        content=content_blocks,
    )
    db_session.add(tailored)
    db_session.commit()

    fetched = db_session.query(TailoredResume).first()
    assert fetched.content[0]["type"] == "summary"
    assert fetched.content[1]["bullets"] == ["Built internal tooling", "Led a small feature team"]
    assert fetched.evaluation.id == evaluation.id


@pytest.mark.db
def test_application_nullable_tailored_resume(db_session):
    job = JobPosting(raw_text="job text")
    db_session.add(job)
    db_session.commit()

    application = Application(job_posting_id=job.id, status="applied")
    db_session.add(application)
    db_session.commit()

    fetched = db_session.query(Application).first()
    assert fetched.tailored_resume_id is None
    assert fetched.job_posting.id == job.id


@pytest.mark.db
def test_blocker_rule_creation(db_session):
    rule = BlockerRule(text="Sample blocker rule", order=1)
    db_session.add(rule)
    db_session.commit()

    fetched = db_session.query(BlockerRule).first()
    assert fetched.text == "Sample blocker rule"
    assert fetched.order == 1


@pytest.mark.db
def test_task_status_defaults_to_pending(db_session):
    task = TaskStatus(task_type="evaluation")
    db_session.add(task)
    db_session.commit()

    fetched = db_session.query(TaskStatus).first()
    assert fetched.status == "pending"


@pytest.mark.db
def test_scoring_factor_creation(db_session):
    factor = ScoringFactor(text="Sample scoring factor", direction="plus", weight=2, order=1)
    db_session.add(factor)
    db_session.commit()

    fetched = db_session.query(ScoringFactor).first()
    assert fetched.text == "Sample scoring factor"
    assert fetched.direction == "plus"
    assert fetched.weight == 2


@pytest.mark.db
def test_form_question_relationship(db_session):
    job = JobPosting(raw_text="job text")
    db_session.add(job)
    db_session.commit()

    application = Application(job_posting_id=job.id, status="draft")
    db_session.add(application)
    db_session.commit()

    question = FormQuestion(
        application_id=application.id,
        question_text="Why do you want this role?",
        answer_type="text",
        answer_text="Sample answer text.",
    )
    db_session.add(question)
    db_session.commit()

    assert application.form_questions[0].question_text == "Why do you want this role?"