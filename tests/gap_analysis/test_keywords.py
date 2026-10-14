import pytest

from core.gap_analysis.keywords import (
    classify_requirements,
    contains_phrase,
    keywords_for_block,
    keywords_for_letter,
    normalize_text,
)


class _FakeProvider:
    def __init__(self, response_text: str = ""):
        self.response_text = response_text
        self.calls = 0

    def call(self, system_prompt, user_prompt, max_tokens=None, **kwargs):
        self.calls += 1
        self.last_prompt = user_prompt
        return self.response_text


_BLOCKS = [
    {"field_path": "summary", "kind": "summary", "label": "Summary", "text": "Built LLM Engineer tooling with Python"},
    {"field_path": "skills", "kind": "skills", "label": "Skills", "text": "Python, SQL"},
]
_RESUME = "Built LLM Engineer tooling with Python Python, SQL"


def _req(text):
    return {"text": text, "priority": "required", "category": "skill", "tier": "P0"}


def _run(provider, requirements, known=None, linkedin="", extra=None):
    return classify_requirements(provider, requirements, _BLOCKS, _RESUME, linkedin, extra, known or [])


@pytest.mark.gap_analysis
def test_normalize_and_contains_phrase():
    assert normalize_text("Node.js, C++ and Python.") == "node.js c++ and python"
    assert contains_phrase(normalize_text("We use Python daily"), "python")
    assert not contains_phrase(normalize_text("Pythonic code"), "python")


@pytest.mark.gap_analysis
def test_exact_match_needs_no_llm_call():
    provider = _FakeProvider()

    result = _run(provider, [_req("Python")])

    assert provider.calls == 0
    assert result[0]["status"] == "exact"
    assert result[0]["original_field_path"] == "summary"


@pytest.mark.gap_analysis
def test_unsupported_bucket_from_the_model_is_treated_as_unknown():
    provider = _FakeProvider('<k i="0" bucket="rephrase" resume="LLM Engineer" suggest="AI Engineer" />')

    result = _run(provider, [_req("Kubernetes")])

    assert result[0]["status"] == "unknown"


@pytest.mark.gap_analysis
def test_can_add_keeps_model_evidence_and_block():
    provider = _FakeProvider('<k i="0" bucket="can_add" evidence="container orchestration" where="summary" />')

    result = _run(provider, [_req("Kubernetes")])

    assert result[0]["status"] == "can_add"
    assert result[0]["evidence"] == "container orchestration"
    assert result[0]["assigned_field_paths"] == ["summary"]


@pytest.mark.gap_analysis
def test_can_add_with_unknown_block_falls_back_to_skills():
    provider = _FakeProvider('<k i="0" bucket="can_add" evidence="proof" where="no such block" />')

    result = _run(provider, [_req("Kubernetes")])

    assert result[0]["assigned_field_paths"] == ["skills"]


@pytest.mark.gap_analysis
def test_unknown_and_missing_verdicts_stay_unknown():
    provider = _FakeProvider('<k i="0" bucket="unknown" />')

    result = _run(provider, [_req("Rust"), _req("Go")])

    assert [item["status"] for item in result] == ["unknown", "unknown"]


@pytest.mark.gap_analysis
def test_known_skill_becomes_can_add_even_if_model_says_unknown():
    provider = _FakeProvider('<k i="0" bucket="unknown" />')

    result = _run(provider, [_req("Docker")], known=["docker"])

    assert result[0]["status"] == "can_add"
    assert result[0]["assigned_field_paths"] == ["skills"]


@pytest.mark.gap_analysis
def test_llm_failure_falls_back_to_known_and_unknown():
    class _Broken:
        def call(self, *args, **kwargs):
            raise RuntimeError("boom")

    result = classify_requirements(
        _Broken(), [_req("Docker"), _req("Rust")], _BLOCKS, _RESUME, "", None, ["Docker"]
    )

    assert {item["text"]: item["status"] for item in result} == {"Docker": "can_add", "Rust": "unknown"}


@pytest.mark.gap_analysis
def test_why_from_the_model_is_kept_for_debugging():
    provider = _FakeProvider('<k i="0" why="no source mentions it" bucket="unknown" />')

    result = _run(provider, [_req("Rust")])

    assert result[0]["why"] == "no source mentions it"


@pytest.mark.gap_analysis
def test_long_linkedin_text_is_sent_to_the_model_in_full():
    provider = _FakeProvider('<k i="0" bucket="unknown" />')
    linkedin = "start " + "filler " * 3000 + "THE_END_MARKER"

    _run(provider, [_req("Rust")], linkedin=linkedin)

    assert "THE_END_MARKER" in provider.last_prompt


@pytest.mark.gap_analysis
def test_greater_than_sign_inside_an_attribute_does_not_cut_the_tag():
    provider = _FakeProvider(
        '<k i="0" why="shows it => same" bucket="can_add" evidence="proof quote" where="summary" />'
    )

    result = _run(provider, [_req("Kubernetes")])

    assert result[0]["status"] == "can_add"
    assert result[0]["evidence"] == "proof quote"
    assert result[0]["why"] == "shows it => same"


@pytest.mark.gap_analysis
def test_linkedin_mention_is_a_hint_for_the_model_not_an_override():
    provider = _FakeProvider('<k i="0" why="only switching providers" bucket="unknown" />')

    result = _run(provider, [_req("APIs")], linkedin="cut the cost by switching APIs")

    assert result[0]["status"] == "unknown"
    assert "mentioned=yes" in provider.last_prompt


@pytest.mark.gap_analysis
def test_title_keywords_are_not_sent_to_the_model():
    provider = _FakeProvider('<k i="0" bucket="can_add" evidence="x" where="skills" />')

    result = _run(provider, [{"text": "Staff Engineer", "priority": "required", "category": "title", "tier": "P0"}])

    assert provider.calls == 0
    assert result[0]["status"] == "unknown"


@pytest.mark.gap_analysis
def test_escaped_characters_in_the_answer_are_unescaped():
    provider = _FakeProvider('<k i="0" why="x" bucket="can_add" evidence="R&amp;D team" where="skills" />')

    result = _run(provider, [_req("Kubernetes")])

    assert result[0]["evidence"] == "R&D team"


@pytest.mark.gap_analysis
def test_keywords_for_block_routes_skills_to_skills_and_the_rest_to_summary():
    items = [
        {"text": "Kafka", "status": "can_add", "category": "tool", "assigned_field_paths": ["experience: A"]},
        {"text": "financial services", "status": "can_add", "category": "domain", "assigned_field_paths": []},
        {"text": "Rust", "status": "unknown", "category": "skill", "assigned_field_paths": []},
        {"text": "Go", "status": "unknown", "category": "skill", "assigned_field_paths": ["skills"]},
        {"text": "Docker", "status": "can_add", "category": "tool", "assigned_field_paths": []},
        {"text": "Staff Engineer", "status": "can_add", "category": "title", "assigned_field_paths": []},
    ]

    items.append(
        {"text": "Terraform", "status": "can_add", "category": "tool", "assigned_field_paths": ["summary"]}
    )

    skills = keywords_for_block(
        items, "skills", "skills", "Languages: Python Docker", "Python Docker", "summary"
    )
    summary = keywords_for_block(
        items, "summary", "summary", "Built things", "Built things Python", "skills"
    )

    assert [item["text"] for item in skills] == ["Kafka", "Go"]
    assert [item["text"] for item in summary] == ["Terraform"]
    letter = keywords_for_letter(items, "skills", "summary")
    assert [item["text"] for item in letter] == ["financial services"]


@pytest.mark.gap_analysis
def test_covered_bucket_becomes_exact_and_is_never_inserted():
    provider = _FakeProvider(
        '<k i="0" why="proof: PostgreSQL (same)" bucket="covered" evidence="PostgreSQL" where="skills" />'
    )

    result = _run(provider, [_req("relational databases")])

    assert provider.calls == 1
    assert result[0]["status"] == "exact"
    assert result[0]["evidence"] == "PostgreSQL"
    assert keywords_for_block(result, "skills", "skills", "PostgreSQL", "PostgreSQL") == []