import pytest

from core.evaluator.pipeline import empty_quick_result, evaluate_job_posting, quick_extract_job_posting


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
<reasoning>BLOCKERS: none. ROLE: matches. GROUP C: none. CAP: 10.</reasoning>
<con>Requires some Kubernetes experience</con>
<con>Slightly more senior scope than usual</con>
<pro>Strong Python and FastAPI match</pro>
<pro>Remote friendly</pro>
<matched_factor id="1">Salary is above the preferred threshold</matched_factor>
<score>8</score>
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

    assert result["score"] == 8
    assert result["verdict"] is True
    assert result["reasoning"].startswith("BLOCKERS: none")
    assert result["cons"] == [
        "Requires some Kubernetes experience",
        "Slightly more senior scope than usual",
    ]
    assert result["pros"] == ["Strong Python and FastAPI match", "Remote friendly"]


@pytest.mark.evaluator
def test_evaluate_job_posting_no_longer_returns_metadata_fields():
    provider = _FakeProvider(_SAMPLE_RESPONSE)

    result = evaluate_job_posting(
        provider, job_posting_text="job", resume_text="resume", linkedin_text="linkedin", blockers=[]
    )

    for key in ["company", "role", "location", "work_mode", "salary", "summary"]:
        assert key not in result


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
def test_evaluate_job_posting_zero_score_means_no_verdict():
    provider = _FakeProvider(_SAMPLE_RESPONSE.replace("<score>8</score>", "<score>0</score>"))

    result = evaluate_job_posting(
        provider, job_posting_text="job", resume_text="resume", linkedin_text="linkedin", blockers=["b"]
    )

    assert result["score"] == 0
    assert result["verdict"] is False


@pytest.mark.evaluator
def test_evaluate_job_posting_handles_missing_score_gracefully():
    provider = _FakeProvider(_SAMPLE_RESPONSE.replace("<score>8</score>", ""))

    result = evaluate_job_posting(
        provider, job_posting_text="job", resume_text="resume", linkedin_text="linkedin", blockers=[]
    )

    assert result["score"] is None
    assert result["verdict"] is False


@pytest.mark.evaluator
def test_evaluate_job_posting_drops_empty_bullets():
    provider = _FakeProvider("<con> </con><con>Real problem</con><pro></pro><score>5</score>")

    result = evaluate_job_posting(
        provider, job_posting_text="job", resume_text="resume", linkedin_text="linkedin", blockers=[]
    )

    assert result["cons"] == ["Real problem"]
    assert result["pros"] == []


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


_SAMPLE_QUICK_RESPONSE = """
<company>Example Corp</company>
<role>Backend Engineer</role>
<location_country>Germany</location_country>
<location_city>Berlin</location_city>
<work_mode>remote</work_mode>
<employment_type>full_time</employment_type>
<salary_min>120000</salary_min>
<salary_max>140000</salary_max>
<salary_currency>USD</salary_currency>
<salary_period>year</salary_period>
<salary_is_estimate>false</salary_is_estimate>
<salary_original_text>$120,000-$140,000/year</salary_original_text>
<tag>Python</tag>
<tag>FastAPI</tag>
<tag>Senior</tag>
<summary>A backend engineering role at a mid-size product company.</summary>
"""


@pytest.mark.evaluator
def test_quick_extract_job_posting_parses_all_fields():
    provider = _FakeProvider(_SAMPLE_QUICK_RESPONSE)

    result = quick_extract_job_posting(provider, job_posting_text="Sample job posting")

    assert result["company"] == "Example Corp"
    assert result["role"] == "Backend Engineer"
    assert result["location"] == "Germany, Berlin"
    assert result["location_country"] == "Germany"
    assert result["location_city"] == "Berlin"
    assert result["work_mode"] == "remote"
    assert result["employment_type"] == "full_time"
    assert result["tags"] == ["Python", "FastAPI", "Senior"]
    assert result["summary"] == "A backend engineering role at a mid-size product company."
    assert result["salary"]["min"] == 120000
    assert result["salary"]["max"] == 140000
    assert result["salary"]["currency"] == "USD"
    assert result["salary"]["period"] == "year"
    assert result["salary"]["is_estimate"] is False
    assert result["salary"]["original_text"] == "$120,000-$140,000/year"


@pytest.mark.evaluator
def test_quick_extract_job_posting_marks_estimated_salary():
    response = _SAMPLE_QUICK_RESPONSE.replace(
        "<salary_is_estimate>false</salary_is_estimate>", "<salary_is_estimate>true</salary_is_estimate>"
    )
    provider = _FakeProvider(response)

    result = quick_extract_job_posting(provider, job_posting_text="job")

    assert result["salary"]["is_estimate"] is True


@pytest.mark.evaluator
def test_quick_extract_job_posting_handles_missing_fields():
    provider = _FakeProvider("<company>Example Corp</company><role>Engineer</role>")

    result = quick_extract_job_posting(provider, job_posting_text="job")

    assert result["tags"] == []
    assert result["work_mode"] is None
    assert result["employment_type"] is None
    assert result["summary"] is None
    assert result["salary"]["min"] is None
    assert result["location"] == "N/A"


@pytest.mark.evaluator
def test_quick_extract_job_posting_passes_prompt_to_provider():
    provider = _FakeProvider(_SAMPLE_QUICK_RESPONSE)

    quick_extract_job_posting(provider, job_posting_text="Unique job posting marker")

    assert "Unique job posting marker" in provider.last_user_prompt


@pytest.mark.evaluator
def test_empty_quick_result_has_safe_defaults():
    result = empty_quick_result()

    assert result["company"] is None
    assert result["tags"] == []
    assert result["salary"]["min"] is None
    assert result["summary"] is None