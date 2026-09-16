import pytest

from core.tailoring.agent_pipeline import run_agent_turn


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
                {"type": "bullet_list", "items": ["Built a model pipeline"]},
            ],
        }
    ],
    "skills": [{"label": "Languages", "items": ["Python", "SQL"]}],
}

_SAMPLE_RESPONSE = """
<message>For this LLM Engineer role, I suggest renaming your title and rewriting the Example Corp bullets to emphasize LLM work.</message>
<change field_path="name" level="soft" change_type="title" kind="text">Sample Name | LLM Engineer</change>
<change field_path="experience[0].content" level="medium" change_type="experience" kind="blocks">
<block type="paragraph">Worked on LLM-based systems.</block>
<block type="bullet_list">
<item>Built an LLM inference pipeline</item>
</block>
</change>
"""


@pytest.mark.tailoring
def test_run_agent_turn_returns_message_and_changes():
    provider = _FakeProvider(_SAMPLE_RESPONSE)

    result = run_agent_turn(
        provider,
        job_posting_text="job",
        resume_content=_SAMPLE_RESUME_CONTENT,
        matched_factors=[],
        conversation_history=[],
    )

    assert "LLM Engineer role" in result["message"]
    assert len(result["changes"]) == 2


@pytest.mark.tailoring
def test_run_agent_turn_parses_text_change_with_original():
    provider = _FakeProvider(_SAMPLE_RESPONSE)

    result = run_agent_turn(
        provider,
        job_posting_text="job",
        resume_content=_SAMPLE_RESUME_CONTENT,
        matched_factors=[],
        conversation_history=[],
    )

    title_change = next(c for c in result["changes"] if c["field_path"] == "name")
    assert title_change["level"] == "soft"
    assert title_change["proposed_text"] == "Sample Name | LLM Engineer"
    assert title_change["original_text"] == "Sample Name | AI Engineer"
    assert title_change["proposed_content"] is None


@pytest.mark.tailoring
def test_run_agent_turn_parses_blocks_change_with_original():
    provider = _FakeProvider(_SAMPLE_RESPONSE)

    result = run_agent_turn(
        provider,
        job_posting_text="job",
        resume_content=_SAMPLE_RESUME_CONTENT,
        matched_factors=[],
        conversation_history=[],
    )

    experience_change = next(c for c in result["changes"] if c["field_path"] == "experience[0].content")
    assert experience_change["level"] == "medium"
    assert experience_change["proposed_content"] == [
        {"type": "paragraph", "text": "Worked on LLM-based systems."},
        {"type": "bullet_list", "items": ["Built an LLM inference pipeline"]},
    ]
    assert "Built a model pipeline" in experience_change["original_text"]


@pytest.mark.tailoring
def test_run_agent_turn_includes_conversation_history_in_prompt():
    provider = _FakeProvider(_SAMPLE_RESPONSE)

    run_agent_turn(
        provider,
        job_posting_text="job",
        resume_content=_SAMPLE_RESUME_CONTENT,
        matched_factors=[],
        conversation_history=[{"role": "assistant", "text": "Earlier proposal text marker"}],
        user_message="Don't touch my job titles",
    )

    assert "Earlier proposal text marker" in provider.last_user_prompt
    assert "Don't touch my job titles" in provider.last_user_prompt


@pytest.mark.tailoring
def test_run_agent_turn_handles_no_changes_proposed():
    response = "<message>Your resume already looks well-aligned, no changes needed.</message>"
    provider = _FakeProvider(response)

    result = run_agent_turn(
        provider,
        job_posting_text="job",
        resume_content=_SAMPLE_RESUME_CONTENT,
        matched_factors=[],
        conversation_history=[],
    )

    assert result["changes"] == []
    assert "no changes needed" in result["message"]