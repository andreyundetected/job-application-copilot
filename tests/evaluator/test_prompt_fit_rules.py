import pytest

from core.evaluator.prompt import render_evaluator_prompt


def _render(blockers=None) -> str:
    return render_evaluator_prompt(
        job_posting_text="job",
        resume_text="resume",
        linkedin_text="linkedin",
        blockers=["Sample blocker one", "Sample blocker two"] if blockers is None else blockers,
    )


def _reasoning_block(prompt: str) -> str:
    return prompt[prompt.index("<reasoning>") : prompt.index("</reasoning>")]


@pytest.mark.evaluator
def test_prompt_contains_four_stages_in_order_with_blockers_last():
    prompt = _render()

    markers = ["STAGE 1 - ROLE", "STAGE 2 - REQUIREMENTS", "STAGE 3 - PREPARATION", "STAGE 4 - BLOCKERS"]
    positions = [prompt.index(marker) for marker in markers]

    assert positions == sorted(positions)


@pytest.mark.evaluator
def test_blocker_list_sits_after_the_procedure_and_before_the_posting():
    prompt = _render()

    assert prompt.index("STAGE 4 - BLOCKERS") < prompt.index("\nHARD BLOCKERS\n") < prompt.index("\nJOB POSTING\n")
    assert "1. Sample blocker one" in prompt
    assert "2. Sample blocker two" in prompt


@pytest.mark.evaluator
def test_prompt_demands_exactly_one_check_per_blocker():
    prompt = _render()

    assert "The list has exactly 2 blockers." in prompt
    assert "Write exactly 2 check tags, numbered as in the list, in the same order" in prompt


@pytest.mark.evaluator
def test_prompt_without_blockers_has_no_count_sentence():
    assert "The list has exactly" not in _render(blockers=[])


@pytest.mark.evaluator
def test_prompt_defines_time_scale_with_scores():
    prompt = _render()

    assert "SCORE SCALE" in prompt
    for line in [
        "- day: under 1 day of preparation. Score 10.",
        "- days: about 4 days. Score 9.",
        "- week: about 1 week. Score 8.",
        "- weeks: 1-2 weeks. Score 7.",
        "- month: 3-4 weeks. Score 6.",
        "- months2: about 2 months. Score 5.",
        "- months4: 3-4 months. Score 4.",
        "- months6: about 6 months. Score 3.",
        "- year: about a year. Score 2.",
    ]:
        assert line in prompt
    assert "The score is exactly the number of the chosen bucket." in prompt


@pytest.mark.evaluator
def test_score_ignores_role_level_and_blockers():
    prompt = _render()

    assert "WHAT THE SCORE IGNORES" in prompt
    assert "A triggered blocker never changes the score, the bucket or the cons." in prompt
    assert "A junior role or an internship is scored by the same preparation rules" in prompt


@pytest.mark.evaluator
def test_prompt_has_no_role_or_level_caps():
    prompt = _render()

    assert "ROLE CAPS" not in prompt
    assert "<closeness>" not in prompt
    assert "<level>" not in prompt
    assert "ceiling" not in prompt


@pytest.mark.evaluator
def test_prompt_has_the_main_test_and_match_levels():
    prompt = _render()

    assert "THE MAIN TEST" in prompt
    assert "already done exactly this work" in prompt
    assert "Neighbouring work is never close." in prompt
    assert "Docker basics are not Kubernetes or cloud operations." in prompt


@pytest.mark.evaluator
def test_prompt_separates_quick_gaps_from_practice_gaps():
    prompt = _render()

    assert "HOW LONG A MISSING SKILL TAKES" in prompt
    assert "Three or more rows with the same value make the bucket one step slower." in prompt


@pytest.mark.evaluator
def test_prompt_has_theme_language_and_years_rules():
    prompt = _render()

    assert "ROLE BUILT AROUND A THEME" in prompt
    assert "months4 at best" in prompt
    assert "PROGRAMMING LANGUAGES" in prompt
    assert "Never treat a new main language as" in prompt
    assert "YEARS OF EXPERIENCE" in prompt
    assert "asks 8, candidate has 2" in prompt


@pytest.mark.evaluator
def test_prompt_makes_the_bucket_follow_the_slowest_row():
    prompt = _render()

    assert "first copy the match value of the slowest row" in prompt
    assert '"day" is allowed only if every row that is not optional is exact or close' in prompt


@pytest.mark.evaluator
def test_prompt_says_silence_never_triggers_a_blocker():
    prompt = _render()

    assert "Silence never triggers a blocker" in prompt
    assert "A bare city name in the header is not evidence of on-site work" in prompt
    assert "When unsure, it is not triggered." in prompt


@pytest.mark.evaluator
def test_prompt_asks_for_short_blocker_names():
    prompt = _render()

    assert "number. blocker: short name | vacancy: exact short quote" in prompt
    assert "2-4 English words" in prompt


@pytest.mark.evaluator
def test_prompt_contains_no_user_specific_blocker_wording():
    prompt = _render(blockers=[]).lower()

    assert "remote" not in prompt
    assert "montenegro" not in prompt


@pytest.mark.evaluator
def test_reasoning_tags_appear_in_the_required_order():
    reasoning = _reasoning_block(_render())

    tags = [
        "<role_thinking>",
        "<role>",
        "<center>",
        "<requirements_thinking>",
        "<requirements>",
        "<prep_thinking>",
        "<bucket>",
        "<blockers_thinking>",
        "<blockers>",
    ]
    positions = [reasoning.index(tag) for tag in tags]

    assert positions == sorted(positions)
    assert "<score_thinking>" not in reasoning


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


@pytest.mark.evaluator
def test_scoring_factors_are_informational_only():
    prompt = render_evaluator_prompt(
        job_posting_text="job",
        resume_text="resume",
        linkedin_text="linkedin",
        blockers=[],
        scoring_factors=[{"id": 1, "text": "Sample factor", "direction": "plus", "weight": 1}],
    )

    assert "A factor never changes the bucket and never changes the score." in prompt