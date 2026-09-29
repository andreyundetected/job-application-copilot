import pytest

from core.evaluator.prompt import render_evaluator_prompt


def _render() -> str:
    return render_evaluator_prompt(
        job_posting_text="job",
        resume_text="resume",
        linkedin_text="linkedin",
        blockers=[],
    )


def _reasoning_block(prompt: str) -> str:
    return prompt[prompt.index("<reasoning>") : prompt.index("</reasoning>")]


@pytest.mark.evaluator
def test_prompt_contains_all_five_stages_in_order():
    prompt = _render()

    markers = [
        "STAGE 1 - BLOCKERS",
        "STAGE 2 - ROLE",
        "STAGE 3 - REQUIREMENTS",
        "STAGE 4 - PREPARATION",
        "STAGE 5 - SCORE",
    ]
    positions = [prompt.index(marker) for marker in markers]

    assert positions == sorted(positions)


@pytest.mark.evaluator
def test_prompt_defines_preparation_buckets_with_score_ranges():
    prompt = _render()

    assert "PREPARATION BUCKETS AND THEIR SCORE RANGES" in prompt
    for score_range in ["Score 10.", "Score 8-9.", "Score 7.", "Score 5-6.", "Score 2-4.", "Score 0-1."]:
        assert score_range in prompt
    assert "The final score must lie inside the range of the chosen bucket." in prompt


@pytest.mark.evaluator
def test_prompt_separates_docs_learnable_skills_from_practice_skills():
    prompt = _render()

    assert "TWO KINDS OF MISSING SKILLS" in prompt
    assert "Learnable from documentation in days" in prompt
    assert "Needs practice" in prompt
    assert "three or more" in prompt


@pytest.mark.evaluator
def test_prompt_treats_a_new_main_language_as_impossible():
    prompt = _render()

    assert "PROGRAMMING LANGUAGES" in prompt
    assert "the bucket is impossible (score 0-1)" in prompt
    assert "Never treat a new main language as" in prompt
    assert "JavaScript and TypeScript" in prompt


@pytest.mark.evaluator
def test_prompt_treats_years_as_a_convention_not_a_literal_number():
    prompt = _render()

    assert "Required years are a convention" in prompt
    assert "asks 8, candidate has 2" in prompt


@pytest.mark.evaluator
def test_prompt_states_role_and_level_caps():
    prompt = _render()

    assert "ROLE CAPS" in prompt
    assert "(cap 8)" in prompt
    assert "(cap 6)" in prompt
    assert "(cap 7)" in prompt
    assert "(cap 2)" in prompt
    assert "can only lower the score, never raise it" in prompt


@pytest.mark.evaluator
def test_prompt_says_silence_never_triggers_a_blocker():
    prompt = _render()

    assert "Silence never triggers a blocker" in prompt
    assert "A bare city name in the header is not evidence of on-site work" in prompt


@pytest.mark.evaluator
def test_prompt_forces_zero_score_on_triggered_blocker():
    prompt = _render()

    assert "A triggered blocker makes the score 0, always." in prompt
    assert "If a blocker was triggered, the score is 0." in prompt


@pytest.mark.evaluator
def test_reasoning_tags_appear_in_the_required_order():
    reasoning = _reasoning_block(_render())

    tags = [
        "<blockers_thinking>",
        "<blockers>",
        "<role_thinking>",
        "<role>",
        "<requirements_thinking>",
        "<requirements>",
        "<prep_thinking>",
        "<bucket>",
        "<score_thinking>",
    ]
    positions = [reasoning.index(tag) for tag in tags]

    assert positions == sorted(positions)


@pytest.mark.evaluator
def test_bucket_tag_does_not_collide_with_prep_thinking_tag():
    prompt = _render()

    assert "<bucket>" in prompt
    assert "<prep>" not in prompt


@pytest.mark.evaluator
def test_prompt_demands_clean_tag_structure():
    prompt = _render()

    assert "Every tag is opened once and closed once with the same name" in prompt
    assert "Never put a tag inside a tag of the same name" in prompt
    assert "no other tags inside" in prompt


@pytest.mark.evaluator
def test_prompt_keeps_old_structure_out():
    prompt = _render()

    assert "STEP 1" not in prompt
    assert "Group C" not in prompt
    assert "SCORING SCALE" not in prompt