import pytest

from core.db.models import QuestionTemplate
from core.questions.pipeline import split_and_prepare_questions


class _FakeProvider:
    def __init__(self, response_text: str):
        self.response_text = response_text

    def call(self, system_prompt: str, user_prompt: str) -> str:
        return self.response_text


def _fake_template(id_, label, trigger_phrases, instructions):
    template = QuestionTemplate(label=label, trigger_phrases=trigger_phrases, instructions=instructions)
    template.id = id_
    return template


@pytest.mark.questions
def test_split_and_prepare_questions_attaches_matched_custom_template():
    split_response = '<question type="document">Why do you want to work at our company?</question>'
    category_response = "<category>none</category>"
    provider = _FakeProvider(split_response)

    # classify_template_category makes its own provider.call for the LLM fallback;
    # since the question doesn't match built-in regexes for cover_letter/summary,
    # it will hit the LLM classify step - stub via a second fake that always returns "none".
    class _SequencedProvider:
        def __init__(self):
            self.calls = 0

        def call(self, system_prompt, user_prompt):
            self.calls += 1
            if self.calls == 1:
                return split_response
            return category_response

    sequenced = _SequencedProvider()
    custom_templates = [
        _fake_template(1, "Why us", ["why do you want to work"], "Mention our product focus.")
    ]

    results = split_and_prepare_questions(sequenced, raw_text="raw form text", custom_templates=custom_templates)

    assert len(results) == 1
    assert results[0]["template_label"] == "Why us"
    assert results[0]["template_instructions"] == "Mention our product focus."


@pytest.mark.questions
def test_split_and_prepare_questions_no_template_match_leaves_fields_none():
    class _SequencedProvider:
        def __init__(self):
            self.calls = 0

        def call(self, system_prompt, user_prompt):
            self.calls += 1
            if self.calls == 1:
                return '<question type="document">Describe a recent project.</question>'
            return "<category>none</category>"

    sequenced = _SequencedProvider()
    custom_templates = [
        _fake_template(1, "Why us", ["why do you want to work"], "Mention our product focus.")
    ]

    results = split_and_prepare_questions(sequenced, raw_text="raw form text", custom_templates=custom_templates)

    assert results[0]["template_label"] is None
    assert results[0]["template_instructions"] is None


@pytest.mark.questions
def test_split_and_prepare_questions_works_with_no_custom_templates():
    class _SequencedProvider:
        def __init__(self):
            self.calls = 0

        def call(self, system_prompt, user_prompt):
            self.calls += 1
            if self.calls == 1:
                return '<question type="document">Tell us about yourself.</question>'
            return "<category>summary</category>"

    sequenced = _SequencedProvider()

    results = split_and_prepare_questions(sequenced, raw_text="raw form text")

    assert results[0]["template_label"] is None
    assert results[0]["category"] == "summary"