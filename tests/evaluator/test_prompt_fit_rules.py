import pytest

from core.evaluator.prompt import render_evaluator_prompt


def _render() -> str:
    return render_evaluator_prompt(
        job_posting_text="job",
        resume_text="resume",
        linkedin_text="linkedin",
        blockers=[],
    )


@pytest.mark.evaluator
def test_prompt_contains_fit_steps_and_groups():
    prompt = _render()

    for marker in ["STEP 1", "STEP 2", "STEP 3", "STEP 4", "STEP 5", "STEP 6", "Group A", "Group B", "Group C", "YEARS RULE"]:
        assert marker in prompt


@pytest.mark.evaluator
def test_prompt_states_caps_for_hard_gaps():
    prompt = _render()

    assert "MINOR hard gap" in prompt
    assert "MAJOR hard gap" in prompt
    assert "at most 4" in prompt
    assert "at most 6" in prompt


@pytest.mark.evaluator
def test_prompt_never_allows_a_language_in_group_b():
    prompt = _render()

    assert "ALWAYS a Group C hard gap" in prompt
    assert "Never reason" in prompt
    assert "never be used" in prompt


@pytest.mark.evaluator
def test_prompt_lists_several_language_examples_not_just_go():
    prompt = _render()

    for language in ["TypeScript", "Kotlin", "C#", "Ruby", "Go", "Rust"]:
        assert language in prompt


@pytest.mark.evaluator
def test_prompt_moves_blocker_check_after_group_c():
    prompt = _render()

    step3_index = prompt.index("STEP 3 - CHECK THE HARD BLOCKERS")
    group_c_index = prompt.index("Group C - HARD GAP")
    assert group_c_index < step3_index


@pytest.mark.evaluator
def test_prompt_requires_quote_for_triggered_blockers():
    prompt = _render()

    assert "you must be able to quote the exact posting text" in prompt


@pytest.mark.evaluator
def test_prompt_forces_zero_score_on_triggered_blocker():
    prompt = _render()

    assert "the score is 0, full stop" in prompt
    assert "overrides every step below" in prompt


@pytest.mark.evaluator
def test_reasoning_tag_orders_role_groups_then_blockers_then_cap():
    prompt = _render()

    reasoning_start = prompt.index("<reasoning>")
    reasoning_end = prompt.index("</reasoning>")
    reasoning_text = prompt[reasoning_start:reasoning_end]

    assert reasoning_text.index("ROLE:") < reasoning_text.index("GROUP C:")
    assert reasoning_text.index("GROUP C:") < reasoning_text.index("BLOCKERS:")
    assert reasoning_text.index("BLOCKERS:") < reasoning_text.index("CAP:")


@pytest.mark.evaluator
def test_prompt_keeps_old_scale_out():
    prompt = _render()

    assert "SCORING SCALE" not in prompt