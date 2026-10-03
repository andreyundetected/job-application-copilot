import pytest

from core.evaluator.checks import parse_blocker_checks, parse_bucket
from core.evaluator.pipeline import evaluate_job_posting

_BLOCKERS = ["Rule one", "Rule two", "Rule three", "Rule four", "Rule five", "Rule six"]

_RAW = """<reasoning>
<bucket>months2</bucket>
<blockers>
<check>1. blocker: ML training | vacancy: not stated | result: not triggered</check>
<check>5. blocker: Office required | vacancy: Hybrid, 3 days in the Berlin office | result: triggered</check>
<check>6. blocker: Work authorization | vacancy: must be a US citizen | result: triggered</check>
</blockers>
</reasoning>
<con>A real problem</con>
<score>5</score>"""


class _FakeProvider:
    def __init__(self, response_text):
        self.response_text = response_text

    def call(self, system_prompt, user_prompt, **kwargs):
        return self.response_text


@pytest.mark.evaluator
def test_parse_blocker_checks_returns_only_triggered():
    result = parse_blocker_checks(_RAW, _BLOCKERS)

    assert [item["number"] for item in result] == [5, 6]
    assert result[0]["name"] == "Office required"
    assert result[0]["text"] == "Rule five"
    assert result[0]["quote"] == "Hybrid, 3 days in the Berlin office"


@pytest.mark.evaluator
def test_not_triggered_is_not_mistaken_for_triggered():
    raw = "<check>2. blocker: X | vacancy: not stated | result: not triggered</check>"

    assert parse_blocker_checks(raw, _BLOCKERS) == []


@pytest.mark.evaluator
def test_not_stated_quote_becomes_empty():
    raw = "<check>3. blocker: X | vacancy: not stated | result: triggered</check>"

    assert parse_blocker_checks(raw, _BLOCKERS)[0]["quote"] == ""


@pytest.mark.evaluator
def test_out_of_range_and_duplicate_numbers_are_dropped():
    raw = (
        "<check>9. blocker: X | vacancy: q | result: triggered</check>"
        "<check>2. blocker: Y | vacancy: q | result: triggered</check>"
        "<check>2. blocker: Z | vacancy: q2 | result: triggered</check>"
    )

    result = parse_blocker_checks(raw, _BLOCKERS)

    assert [item["number"] for item in result] == [2]
    assert result[0]["name"] == "Y"


@pytest.mark.evaluator
def test_parse_without_blocker_texts_keeps_numbers():
    assert [item["number"] for item in parse_blocker_checks(_RAW)] == [5, 6]


@pytest.mark.evaluator
def test_parse_bucket_takes_the_last_bucket():
    assert parse_bucket(_RAW) == "months2"
    assert parse_bucket("<bucket>day</bucket><bucket>week</bucket>") == "week"
    assert parse_bucket("nothing") == "?"


@pytest.mark.evaluator
def test_evaluate_job_posting_returns_blockers_without_touching_score():
    result = evaluate_job_posting(
        _FakeProvider(_RAW),
        job_posting_text="job",
        resume_text="resume",
        linkedin_text="linkedin",
        blockers=_BLOCKERS,
    )

    assert result["score"] == 5
    assert [item["number"] for item in result["triggered_blockers"]] == [5, 6]
    assert result["verdict"] is False


@pytest.mark.evaluator
def test_evaluate_job_posting_verdict_true_without_blockers():
    result = evaluate_job_posting(
        _FakeProvider("<score>8</score>"),
        job_posting_text="job",
        resume_text="resume",
        linkedin_text="linkedin",
        blockers=_BLOCKERS,
    )

    assert result["triggered_blockers"] == []
    assert result["verdict"] is True