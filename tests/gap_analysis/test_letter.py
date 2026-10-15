import pytest

import config
from core.gap_analysis.keywords import classify_requirements
from core.gap_analysis.letter import generate_cover_letter



class _FakeProvider:
    def __init__(self, response_text):
        self.response_text = response_text
        self.last_prompt = ""
        self.calls = 0
        self.seen_temperature = "unset"

    def call(self, system_prompt, user_prompt, max_tokens=None, **kwargs):
        self.calls += 1
        self.last_prompt = user_prompt
        self.seen_temperature = kwargs.get("temperature", "unset")
        return self.response_text


_BLOCKS = [
    {"field_path": "summary", "kind": "summary", "label": "Summary", "text": "Built agents"},
    {"field_path": "skills", "kind": "skills", "label": "Skills", "text": "Python"},
]


def _req(text, category):
    return {"text": text, "priority": "required", "category": category, "tier": "P1"}


def _classify(provider, requirements):
    return classify_requirements(provider, requirements, _BLOCKS, "Built agents Python", "", None, [])


def _generate(provider, **overrides):
    values = {
        "company": "Acme",
        "job_title": "AI Engineer",
        "job_posting_text": "posting",
        "resume_text": "resume",
        "linkedin_text": "",
        "extra_info": None,
        "topics": [],
        "not_proven": [],
        "notes": "",
    }
    values.update(overrides)
    return generate_cover_letter(provider, **values)


@pytest.mark.gap_analysis
def test_letter_destination_from_the_model_is_kept():
    provider = _FakeProvider('<k i="0" why="x" bucket="can_add" evidence="served banks" where="letter" />')

    result = _classify(provider, [_req("financial services", "domain")])

    assert result[0]["assigned_field_paths"] == ["letter"]
    assert result[0]["evidence"] == "served banks"


@pytest.mark.gap_analysis
def test_missing_destination_falls_back_by_category():
    provider = _FakeProvider(
        '<k i="0" why="x" bucket="can_add" evidence="a" />'
        '<k i="1" why="x" bucket="can_add" evidence="b" />'
    )

    result = _classify(provider, [_req("Terraform", "tool"), _req("financial services", "domain")])

    assert result[0]["assigned_field_paths"] == ["skills"]
    assert result[1]["assigned_field_paths"] == ["letter"]


@pytest.mark.gap_analysis
def test_letter_text_is_taken_from_the_tag_and_the_plan_is_dropped():
    provider = _FakeProvider("noise <plan>my plan</plan> <letter>\nDear Team,\n\nHello.   \n</letter> noise")

    assert _generate(provider) == "Dear Team,\n\nHello."


@pytest.mark.gap_analysis
def test_letter_without_tag_uses_the_whole_answer():
    assert _generate(_FakeProvider("Dear Team, hello.")) == "Dear Team, hello."


@pytest.mark.gap_analysis
def test_text_after_the_plan_is_used_when_the_letter_tag_is_missing():
    assert _generate(_FakeProvider("<plan>p</plan>\nDear Team, hello.")) == "Dear Team, hello."


@pytest.mark.gap_analysis
def test_an_unclosed_letter_tag_is_still_read():
    assert _generate(_FakeProvider("<letter>Dear Team, hello.")) == "Dear Team, hello."


@pytest.mark.gap_analysis
def test_empty_letter_raises():
    with pytest.raises(ValueError):
        _generate(_FakeProvider("<letter>  </letter>"))


@pytest.mark.gap_analysis
def test_the_model_is_called_once():
    provider = _FakeProvider("<letter>Dear Team.</letter>")

    _generate(provider)

    assert provider.calls == 1


@pytest.mark.gap_analysis
def test_topics_not_proven_name_and_contacts_reach_the_prompt():
    provider = _FakeProvider("<letter>x</letter>")

    _generate(
        provider,
        topics=['client-facing work (basis: "delivered to a client")'],
        not_proven=["Snowflake"],
        candidate_name="Jane Sample",
        contacts=["sample@example.com", "github.com/sampleuser"],
    )

    assert "delivered to a client" in provider.last_prompt
    assert "Snowflake" in provider.last_prompt
    assert '"Jane Sample"' in provider.last_prompt
    assert "sample@example.com" in provider.last_prompt
    assert "github.com/sampleuser" in provider.last_prompt


@pytest.mark.gap_analysis
def test_notes_and_writing_preferences_come_last_before_the_output_format():
    provider = _FakeProvider("<letter>x</letter>")

    _generate(provider, notes="keep it warm", writing_preferences="never mention salary")

    prompt = provider.last_prompt
    assert prompt.index("GREETING AND SIGNATURE") < prompt.index("keep it warm") < prompt.index("OUTPUT FORMAT")
    assert prompt.index("GREETING AND SIGNATURE") < prompt.index("never mention salary") < prompt.index("OUTPUT FORMAT")


@pytest.mark.gap_analysis
def test_instruction_block_is_absent_without_notes_or_preferences():
    provider = _FakeProvider("<letter>x</letter>")

    _generate(provider)

    assert "MANDATORY INSTRUCTIONS" not in provider.last_prompt


@pytest.mark.gap_analysis
def test_russian_posting_switches_the_letter_language():
    provider = _FakeProvider("<letter>x</letter>")

    _generate(provider, job_posting_text="Мы ищем инженера по поиску и ретривалу для команды поддержки.")

    assert "Russian" in provider.last_prompt
    assert "officialese" in provider.last_prompt


@pytest.mark.gap_analysis
def test_letter_uses_the_configured_temperature_only_during_the_call():
    provider = _FakeProvider("<letter>x</letter>")

    _generate(provider)

    assert provider.seen_temperature == config.LETTER_TEMPERATURE


@pytest.mark.gap_analysis
def test_explicit_temperature_wins():
    provider = _FakeProvider("<letter>x</letter>")

    _generate(provider, temperature=1.1)

    assert provider.seen_temperature == 1.1