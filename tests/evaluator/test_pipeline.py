import pytest

from core.evaluator.pipeline import evaluate_job_posting


class _FakeProvider:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.last_system_prompt = None
        self.last_user_prompt = None

    def call(self, system_prompt: str, user_prompt: str) -> str:
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        return self.response_text


_SAMPLE_RESPONSE = """
<reasoning>Matches the candidate's stack and seniority well.</reasoning>
<company>Example Corp</company>
<role>Backend Engineer</role>
<score>8</score>
<location>Berlin, Germany</location>
<work_mode>remote</work_mode>
<salary_min>120000</salary_min>
<salary_max>120000</salary_max>
<salary_currency>USD</salary_currency>
<salary_period>year</salary_period>
<salary_is_estimate>false</salary_is_estimate>
<salary_original_text>$120,000/year</salary_original_text>
<matched_factor id="1">Salary is above the preferred threshold</matched_factor>
<con>Requires some Kubernetes experience</con>
<con>Slightly more senior scope than usual</con>
<pro>Strong Python and FastAPI match</pro>
<pro>Remote friendly</pro>
<summary>A backend engineering role at a mid-size product company.</summary>
"""

_SAMPLE_SCORING_FACTORS = [
    {"id": 1, "text": "Salary above $120k", "direction": "plus", "weight": 2},
    {"id": 2, "text": "Requires Linux administration", "direction": "minus", "weight": 1},
]


@pytest.mark.evaluator
def test_evaluate_job_posting_parses_all_fields():
    provider = _FakeProvider(_SAMPLE_RESPONSE)

    result = evaluate_job_posting(
        provider,
        job_posting_text="Sample job posting",
        resume_text="Sample resume",
        linkedin_text="Sample linkedin",
        blockers=["Sample blocker"],
        scoring_factors=_SAMPLE_SCORING_FACTORS,
    )

    assert result["company"] == "Example Corp"
    assert result["role"] == "Backend Engineer"
    assert result["score"] == 8
    assert result["location"] == "Berlin, Germany"
    assert result["work_mode"] == "remote"
    assert result["salary"]["min"] == 120000
    assert result["salary"]["max"] == 120000
    assert result["salary"]["currency"] == "USD"
    assert result["salary"]["period"] == "year"
    assert result["salary"]["is_estimate"] is False
    assert result["salary"]["original_text"] == "$120,000/year"
    assert result["cons"] == [
        "Requires some Kubernetes experience",
        "Slightly more senior scope than usual",
    ]
    assert result["pros"] == [
        "Strong Python and FastAPI match",
        "Remote friendly",
    ]
    assert result["summary"] == "A backend engineering role at a mid-size product company."
    assert result["verdict"] is True


@pytest.mark.evaluator
def test_evaluate_job_posting_returns_matched_factors():
    provider = _FakeProvider(_SAMPLE_RESPONSE)

    result = evaluate_job_posting(
        provider,
        job_posting_text="job",
        resume_text="resume",
        linkedin_text="linkedin",
        blockers=[],
        scoring_factors=_SAMPLE_SCORING_FACTORS,
    )

    assert len(result["matched_factors"]) == 1
    matched = result["matched_factors"][0]
    assert matched["id"] == 1
    assert matched["text"] == "Salary above $120k"
    assert matched["direction"] == "plus"
    assert matched["weight"] == 2
    assert matched["note"] == "Salary is above the preferred threshold"


@pytest.mark.evaluator
def test_evaluate_job_posting_ignores_unknown_factor_ids():
    response = _SAMPLE_RESPONSE.replace(
        '<matched_factor id="1">Salary is above the preferred threshold</matched_factor>',
        '<matched_factor id="999">Unknown factor</matched_factor>',
    )
    provider = _FakeProvider(response)

    result = evaluate_job_posting(
        provider,
        job_posting_text="job",
        resume_text="resume",
        linkedin_text="linkedin",
        blockers=[],
        scoring_factors=_SAMPLE_SCORING_FACTORS,
    )

    assert result["matched_factors"] == []


@pytest.mark.evaluator
def test_evaluate_job_posting_no_matched_factors_when_none_apply():
    response = _SAMPLE_RESPONSE.replace(
        '<matched_factor id="1">Salary is above the preferred threshold</matched_factor>\n',
        "",
    )
    provider = _FakeProvider(response)

    result = evaluate_job_posting(
        provider,
        job_posting_text="job",
        resume_text="resume",
        linkedin_text="linkedin",
        blockers=[],
        scoring_factors=_SAMPLE_SCORING_FACTORS,
    )

    assert result["matched_factors"] == []


@pytest.mark.evaluator
def test_evaluate_job_posting_zero_score_means_no_verdict():
    response = _SAMPLE_RESPONSE.replace("<score>8</score>", "<score>0</score>")
    provider = _FakeProvider(response)

    result = evaluate_job_posting(
        provider,
        job_posting_text="Sample job posting",
        resume_text="Sample resume",
        linkedin_text="Sample linkedin",
        blockers=["Sample blocker"],
    )

    assert result["score"] == 0
    assert result["verdict"] is False


@pytest.mark.evaluator
def test_evaluate_job_posting_passes_prompt_to_provider():
    provider = _FakeProvider(_SAMPLE_RESPONSE)

    evaluate_job_posting(
        provider,
        job_posting_text="Unique job posting marker",
        resume_text="resume",
        linkedin_text="linkedin",
        blockers=[],
    )

    assert "Unique job posting marker" in provider.last_user_prompt


@pytest.mark.evaluator
def test_evaluate_job_posting_handles_missing_score_gracefully():
    response = _SAMPLE_RESPONSE.replace("<score>8</score>", "")
    provider = _FakeProvider(response)

    result = evaluate_job_posting(
        provider,
        job_posting_text="job",
        resume_text="resume",
        linkedin_text="linkedin",
        blockers=[],
    )

    assert result["score"] is None
    assert result["verdict"] is False


@pytest.mark.evaluator
def test_evaluate_job_posting_marks_estimated_salary():
    response = _SAMPLE_RESPONSE.replace(
        "<salary_is_estimate>false</salary_is_estimate>",
        "<salary_is_estimate>true</salary_is_estimate>",
    ).replace(
        "<salary_original_text>$120,000/year</salary_original_text>",
        "<salary_original_text>Not stated in posting - estimated based on role, seniority, company size and market</salary_original_text>",
    )
    provider = _FakeProvider(response)

    result = evaluate_job_posting(
        provider,
        job_posting_text="job",
        resume_text="resume",
        linkedin_text="linkedin",
        blockers=[],
    )

    assert result["salary"]["is_estimate"] is True
    assert "estimated" in result["salary"]["original_text"].lower()