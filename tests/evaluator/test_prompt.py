import pytest

from core.evaluator.prompt import render_evaluator_prompt


@pytest.mark.evaluator
def test_prompt_includes_job_posting_and_resume():
    prompt = render_evaluator_prompt(
        job_posting_text="Sample job posting text",
        resume_text="Sample resume text",
        linkedin_text="Sample linkedin text",
        blockers=["Sample blocker one", "Sample blocker two"],
    )

    assert "Sample job posting text" in prompt
    assert "Sample resume text" in prompt
    assert "Sample linkedin text" in prompt
    assert "Sample blocker one" in prompt
    assert "Sample blocker two" in prompt


@pytest.mark.evaluator
def test_prompt_numbers_blockers_in_order():
    prompt = render_evaluator_prompt(
        job_posting_text="job",
        resume_text="resume",
        linkedin_text="linkedin",
        blockers=["First rule", "Second rule"],
    )

    assert "1. First rule" in prompt
    assert "2. Second rule" in prompt


@pytest.mark.evaluator
def test_prompt_includes_contacts_and_extra_info_when_given():
    prompt = render_evaluator_prompt(
        job_posting_text="job",
        resume_text="resume",
        linkedin_text="linkedin",
        blockers=[],
        contacts=["sample@example.com", "github.com/sampleuser"],
        extra_info="Sample extra context.",
    )

    assert "sample@example.com" in prompt
    assert "github.com/sampleuser" in prompt
    assert "Sample extra context." in prompt


@pytest.mark.evaluator
def test_prompt_omits_extra_info_section_when_not_given():
    prompt = render_evaluator_prompt(
        job_posting_text="job",
        resume_text="resume",
        linkedin_text="linkedin",
        blockers=[],
    )

    assert "ADDITIONAL CONTEXT ABOUT THE CANDIDATE" not in prompt


@pytest.mark.evaluator
def test_prompt_contains_output_format_tags():
    prompt = render_evaluator_prompt(
        job_posting_text="job",
        resume_text="resume",
        linkedin_text="linkedin",
        blockers=[],
    )

    tags = [
        "<reasoning>",
        "<company>",
        "<role>",
        "<score>",
        "<location>",
        "<work_mode>",
        "<salary_min>",
        "<salary_max>",
        "<salary_currency>",
        "<salary_period>",
        "<salary_is_estimate>",
        "<salary_original_text>",
        "<con>",
        "<pro>",
        "<summary>",
    ]
    for tag in tags:
        assert tag in prompt