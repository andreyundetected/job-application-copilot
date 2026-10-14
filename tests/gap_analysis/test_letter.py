import pytest

from core.gap_analysis.keywords import classify_requirements
from core.gap_analysis.letter import generate_cover_letter, validate_letter


class _FakeProvider:
    def __init__(self, response_text):
        self.response_text = response_text
        self.last_prompt = ""

    def call(self, system_prompt, user_prompt, max_tokens=None, **kwargs):
        self.last_prompt = user_prompt
        return self.response_text


class _SequenceProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.prompts = []

    def call(self, system_prompt, user_prompt, max_tokens=None, **kwargs):
        self.calls += 1
        self.prompts.append(user_prompt)
        return self.responses.pop(0)


_BLOCKS = [
    {"field_path": "summary", "kind": "summary", "label": "Summary", "text": "Built agents"},
    {"field_path": "skills", "kind": "skills", "label": "Skills", "text": "Python"},
]


def _req(text, category):
    return {"text": text, "priority": "required", "category": category, "tier": "P1"}


def _classify(provider, requirements):
    return classify_requirements(provider, requirements, _BLOCKS, "Built agents Python", "", None, [])


def _good_letter(words=280):
    body = " ".join(["pipeline"] * words)
    return f"<letter>\nDear Hiring Team,\n\nYour retrieval work needs {body}.\n\nBest regards,\nSample Name\n</letter>"


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
def test_letter_text_is_taken_from_the_tag():
    provider = _FakeProvider("noise <letter>\nDear Team,\n\nHello.   \n</letter> noise")

    text = generate_cover_letter(provider, "Acme", "AI Engineer", "posting", "resume", "", None, [], [], "")

    assert text == "Dear Team,\n\nHello."


@pytest.mark.gap_analysis
def test_letter_without_tag_uses_the_whole_answer():
    provider = _FakeProvider("Dear Team, hello.")

    assert generate_cover_letter(provider, "", "", "posting", "resume", "", None, [], [], "") == "Dear Team, hello."


@pytest.mark.gap_analysis
def test_empty_letter_raises():
    provider = _FakeProvider("<letter>  </letter>")

    with pytest.raises(ValueError):
        generate_cover_letter(provider, "", "", "posting", "resume", "", None, [], [], "")


@pytest.mark.gap_analysis
def test_topics_not_proven_and_notes_reach_the_prompt():
    provider = _FakeProvider("<letter>x</letter>")

    generate_cover_letter(
        provider,
        "Acme",
        "AI Engineer",
        "posting",
        "resume",
        "",
        None,
        ['client-facing work (basis: "delivered to a client")'],
        ["Snowflake"],
        "keep it warm",
    )

    assert 'delivered to a client' in provider.last_prompt
    assert "Snowflake" in provider.last_prompt
    assert "keep it warm" in provider.last_prompt


@pytest.mark.gap_analysis
def test_contacts_reach_the_prompt():
    provider = _FakeProvider(_good_letter())

    generate_cover_letter(
        provider, "Acme", "AI Engineer", "posting", "resume", "", None, [], [], "",
        contacts=["sample@example.com", "github.com/sampleuser"],
    )

    assert "sample@example.com" in provider.last_prompt
    assert "github.com/sampleuser" in provider.last_prompt


@pytest.mark.gap_analysis
def test_validate_flags_generic_opener():
    text = "Dear Team,\n\nI am writing to apply for the role. " + "word " * 280

    issues = validate_letter(text)

    assert any("first sentence" in issue for issue in issues)


@pytest.mark.gap_analysis
def test_validate_flags_length_and_buzzwords():
    assert any("too short" in issue for issue in validate_letter("Dear Team, hello."))
    assert any("too long" in issue for issue in validate_letter("word " * 450))
    assert any("buzzwords" in issue for issue in validate_letter("I am thrilled " + "word " * 280))


@pytest.mark.gap_analysis
def test_validate_passes_a_clean_letter():
    clean = "Dear Hiring Team,\n\nYour retrieval stack needs " + "pipeline " * 280

    assert validate_letter(clean) == []


@pytest.mark.gap_analysis
def test_letter_is_regenerated_once_with_the_problems_listed():
    bad = "<letter>I am writing to apply for the role. " + "word " * 280 + "</letter>"
    provider = _SequenceProvider([bad, _good_letter()])

    text = generate_cover_letter(provider, "Acme", "AI Engineer", "posting", "resume", "", None, [], [], "")

    assert provider.calls == 2
    assert "FIX THESE PROBLEMS" not in provider.prompts[0]
    assert "FIX THESE PROBLEMS" in provider.prompts[1]
    assert "generic opener" in provider.prompts[1]
    assert "Dear Hiring Team" in text


@pytest.mark.gap_analysis
def test_clean_letter_needs_a_single_call():
    provider = _SequenceProvider([_good_letter()])

    generate_cover_letter(provider, "Acme", "AI Engineer", "posting", "resume", "", None, [], [], "")

    assert provider.calls == 1