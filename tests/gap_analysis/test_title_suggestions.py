import pytest

from core.gap_analysis.title_suggestions import suggest_title_changes, with_work_context


class _FakeProvider:
    def __init__(self, response_text):
        self.response_text = response_text
        self.calls = 0
        self.last_prompt = ""

    def call(self, system_prompt, user_prompt, max_tokens=None, **kwargs):
        self.calls += 1
        self.last_prompt = user_prompt
        return self.response_text


def _targets():
    return [
        {"key": "title:Acme", "kind": "experience", "company": "Acme", "current": "LLM Engineer"},
        {"key": "title:Beta", "kind": "experience", "company": "Beta", "current": "Backend Developer"},
    ]


@pytest.mark.gap_analysis
def test_changed_and_same_titles_are_both_returned_with_reasons():
    provider = _FakeProvider(
        '<title_suggestion id="0" status="changed" reason="same kind of work">AI Engineer</title_suggestion>'
        '<title_suggestion id="1" status="same" reason="different profession">Backend Developer</title_suggestion>'
    )

    result = suggest_title_changes(provider, _targets(), "posting", {}, "AI Engineer")

    assert [item["changed"] for item in result] == [True, False]
    assert result[0]["suggested"] == "AI Engineer"
    assert result[0]["reason"] == "same kind of work"
    assert result[1]["suggested"] == "Backend Developer"
    assert result[1]["reason"] == "different profession"


@pytest.mark.gap_analysis
def test_missing_status_falls_back_to_comparing_the_text():
    provider = _FakeProvider('<title_suggestion id="0">AI Engineer</title_suggestion>')

    result = suggest_title_changes(provider, _targets(), "posting", {}, "AI Engineer")

    assert len(result) == 1
    assert result[0]["changed"] is True


@pytest.mark.gap_analysis
def test_escaped_ampersand_is_unescaped():
    provider = _FakeProvider(
        '<title_suggestion id="0" status="changed" reason="x">AI Engineer &amp; Founder</title_suggestion>'
    )

    result = suggest_title_changes(provider, _targets(), "posting", {}, "AI Engineer")

    assert result[0]["suggested"] == "AI Engineer & Founder"


@pytest.mark.gap_analysis
def test_rejections_work_text_and_target_role_reach_the_prompt():
    provider = _FakeProvider("")
    targets = with_work_context(
        _targets(),
        [{"field_path": "experience: Acme", "kind": "exp_body", "label": "Acme", "text": "Built agents for clients"}],
    )
    rejections = [{"original": "AI Engineer", "rejected": "Full-Stack Engineer", "comment": "frontend was not mine"}]

    suggest_title_changes(provider, targets, "posting", {}, "Backend Engineer", rejections)

    assert "Backend Engineer" in provider.last_prompt
    assert "Built agents for clients" in provider.last_prompt
    assert "Full-Stack Engineer" in provider.last_prompt
    assert "frontend was not mine" in provider.last_prompt


@pytest.mark.gap_analysis
def test_work_context_maps_title_keys_to_experience_and_summary_blocks():
    targets = [
        {"key": "title:main", "kind": "main", "current": "Name | AI Engineer"},
        {"key": "title:Acme", "kind": "experience", "company": "Acme", "current": "LLM Engineer"},
    ]
    blocks = [
        {"field_path": "summary", "text": "Builds agents"},
        {"field_path": "experience: Acme", "text": "Shipped   a pipeline"},
    ]

    result = with_work_context(targets, blocks)

    assert result[0]["work"] == "Builds agents"
    assert result[1]["work"] == "Shipped a pipeline"


@pytest.mark.gap_analysis
def test_no_targets_make_no_call():
    provider = _FakeProvider("")

    assert suggest_title_changes(provider, [], "posting") == []
    assert provider.calls == 0