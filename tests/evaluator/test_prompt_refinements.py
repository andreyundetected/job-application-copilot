import pytest

from core.evaluator.prompt import render_evaluator_prompt


def _render() -> str:
    return render_evaluator_prompt(
        job_posting_text="job",
        resume_text="resume",
        linkedin_text="linkedin",
        blockers=["Sample blocker one"],
    )


@pytest.mark.evaluator
def test_optional_rows_never_decide_the_bucket():
    prompt = _render()

    assert "match: optional: weeks" in prompt
    assert "Optional rows never decide the bucket and never go into the cons." in prompt
    assert "the slowest row that is not optional" in prompt


@pytest.mark.evaluator
def test_years_count_only_from_named_work():
    prompt = _render()

    assert "Count years only from a named project or job" in prompt
    assert 'The summary line "N years of development"' in prompt
    assert 'A summary line such as "N years of development" is never evidence' in prompt


@pytest.mark.evaluator
def test_skill_blockers_follow_their_own_qualifiers():
    assert "Follow the blocker's own qualifiers" in _render()


@pytest.mark.evaluator
def test_thinking_tags_forbid_self_corrections():
    assert "Never write drafts, doubts or self-corrections inside a thinking tag" in _render()


@pytest.mark.evaluator
def test_cons_never_contain_blockers_or_quick_gaps():
    prompt = _render()

    assert "Never list a day or days gap. Never write a blocker as a con." in prompt