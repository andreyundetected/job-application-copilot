import pytest

from core.tailoring.pipeline import propose_medium_changes, propose_soft_changes


class _FakeProvider:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.last_user_prompt = None

    def call(self, system_prompt: str, user_prompt: str) -> str:
        self.last_user_prompt = user_prompt
        return self.response_text


_SAMPLE_RESUME_CONTENT = {
    "name": "Sample Name | AI Engineer",
    "summary": "Sample summary about AI work.",
    "experience": [
        {
            "company": "Example Corp",
            "role": "AI Engineer",
            "dates": "2023-2025",
            "content": [
                {"type": "paragraph", "text": "Worked on AI systems."},
                {"type": "bullet_list", "items": ["Built a model pipeline", "Improved accuracy by a wide margin"]},
            ],
        }
    ],
    "skills": [
        {"label": "Languages", "items": ["Python", "SQL"]},
        {"label": "Frameworks", "items": ["FastAPI", "PyTorch"]},
    ],
}

_SAMPLE_SOFT_RESPONSE = """
<title_rewrite>Sample Name | LLM Engineer</title_rewrite>
<experience_title company="Example Corp">LLM Engineer</experience_title>
<skill_group label="Languages">
<item>Python</item>
</skill_group>
<skill_group label="Frameworks">
<item>PyTorch</item>
<item>FastAPI</item>
</skill_group>
"""

_SAMPLE_MEDIUM_RESPONSE = """
<summary_rewrite>Sample summary rewritten around LLM engineering.</summary_rewrite>
<experience_rewrite company="Example Corp">
<block type="paragraph">Worked on LLM-based systems.</block>
<block type="bullet_list">
<item>Built an LLM inference pipeline</item>
</block>
</experience_rewrite>
"""


@pytest.mark.tailoring
def test_propose_soft_changes_returns_title_and_experience_title():
    provider = _FakeProvider(_SAMPLE_SOFT_RESPONSE)

    changes = propose_soft_changes(
        provider,
        job_posting_text="job",
        resume_content=_SAMPLE_RESUME_CONTENT,
        matched_factors=[],
    )

    title_change = next(c for c in changes if c["change_type"] == "title")
    assert title_change["level"] == "soft"
    assert title_change["proposed_text"] == "Sample Name | LLM Engineer"
    assert title_change["original_text"] == "Sample Name | AI Engineer"

    exp_title_change = next(c for c in changes if c["change_type"] == "experience_title")
    assert exp_title_change["target_ref"] == "Example Corp"
    assert exp_title_change["proposed_text"] == "LLM Engineer"
    assert exp_title_change["original_text"] == "AI Engineer"


@pytest.mark.tailoring
def test_propose_soft_changes_returns_skills_change():
    provider = _FakeProvider(_SAMPLE_SOFT_RESPONSE)

    changes = propose_soft_changes(
        provider,
        job_posting_text="job",
        resume_content=_SAMPLE_RESUME_CONTENT,
        matched_factors=[],
    )

    skills_change = next(c for c in changes if c["change_type"] == "skills")
    assert "PyTorch" in skills_change["proposed_text"]
    assert skills_change["level"] == "soft"


@pytest.mark.tailoring
def test_propose_soft_changes_skips_unchanged_experience_title():
    response = _SAMPLE_SOFT_RESPONSE.replace(
        '<experience_title company="Example Corp">LLM Engineer</experience_title>\n', ""
    )
    provider = _FakeProvider(response)

    changes = propose_soft_changes(
        provider,
        job_posting_text="job",
        resume_content=_SAMPLE_RESUME_CONTENT,
        matched_factors=[],
    )

    assert not any(c["change_type"] == "experience_title" for c in changes)


@pytest.mark.tailoring
def test_propose_medium_changes_returns_summary_and_experience():
    provider = _FakeProvider(_SAMPLE_MEDIUM_RESPONSE)

    changes = propose_medium_changes(
        provider,
        job_posting_text="job",
        resume_content=_SAMPLE_RESUME_CONTENT,
        matched_factors=[],
        keywords=["LLM", "inference"],
    )

    summary_change = next(c for c in changes if c["change_type"] == "summary")
    assert summary_change["level"] == "medium"
    assert "LLM engineering" in summary_change["proposed_text"]

    experience_change = next(c for c in changes if c["change_type"] == "experience")
    assert experience_change["target_ref"] == "Example Corp"
    assert "Built an LLM inference pipeline" in experience_change["proposed_text"]
    assert "Built a model pipeline" in experience_change["original_text"]


@pytest.mark.tailoring
def test_propose_medium_changes_skips_entries_without_rewrite():
    response = "<summary_rewrite>Only summary changed.</summary_rewrite>"
    provider = _FakeProvider(response)

    changes = propose_medium_changes(
        provider,
        job_posting_text="job",
        resume_content=_SAMPLE_RESUME_CONTENT,
        matched_factors=[],
        keywords=[],
    )

    assert len(changes) == 1
    assert changes[0]["change_type"] == "summary"


@pytest.mark.tailoring
def test_propose_soft_changes_passes_job_posting_to_provider():
    provider = _FakeProvider(_SAMPLE_SOFT_RESPONSE)

    propose_soft_changes(
        provider,
        job_posting_text="Unique job posting marker",
        resume_content=_SAMPLE_RESUME_CONTENT,
        matched_factors=[],
    )

    assert "Unique job posting marker" in provider.last_user_prompt