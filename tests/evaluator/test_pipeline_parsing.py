import pytest

from core.evaluator.pipeline import evaluate_job_posting


class _FakeProvider:
    def __init__(self, response_text: str):
        self.response_text = response_text

    def call(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        return self.response_text


def _evaluate(response_text: str) -> dict:
    return evaluate_job_posting(
        _FakeProvider(response_text),
        job_posting_text="job",
        resume_text="resume",
        linkedin_text="linkedin",
        blockers=[],
    )


_BROKEN_TAGS = """<reasoning>
<blockers_thinking>Thinking.</blockers_thinking>
<prep_thinking>Thinking.</prep_thinking>
<prep>
<prep>months</prep>
</prep_thinking>
<score_thinking>Thinking.</score_thinking>
</reasoning>
<con>
<bullet>Needs a paradigm shift.</bullet>
</con>
<pro>
<bullet>Strong agent systems record.</bullet>
<bullet>Strong startup experience.</bullet>
</pro>
<score>3</score>"""


@pytest.mark.evaluator
def test_score_and_bullets_survive_broken_tag_nesting():
    result = _evaluate(_BROKEN_TAGS)

    assert result["score"] == 3
    assert result["cons"] == ["Needs a paradigm shift."]
    assert result["pros"] == ["Strong agent systems record.", "Strong startup experience."]
    assert result["verdict"] is True


@pytest.mark.evaluator
def test_last_score_tag_wins():
    result = _evaluate("<reasoning>x</reasoning><score>9</score><score>4</score>")

    assert result["score"] == 4


@pytest.mark.evaluator
def test_score_is_clamped_to_ten():
    result = _evaluate("<score>15</score>")

    assert result["score"] == 10


@pytest.mark.evaluator
def test_score_thinking_tag_is_not_mistaken_for_score():
    result = _evaluate("<score_thinking>7</score_thinking>")

    assert result["score"] is None
    assert result["verdict"] is False


@pytest.mark.evaluator
def test_nested_tags_inside_con_are_stripped():
    result = _evaluate("<con>A <b>real</b> problem.</con><score>5</score>")

    assert result["cons"] == ["A real problem."]