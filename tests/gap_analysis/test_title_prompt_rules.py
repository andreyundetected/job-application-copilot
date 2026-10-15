import pytest

from core.gap_analysis.title_suggestions import suggest_title_changes


class _FakeProvider:
    def __init__(self):
        self.last_prompt = ""

    def call(self, system_prompt, user_prompt, max_tokens=None, **kwargs):
        self.last_prompt = user_prompt
        return ""


def _prompt():
    provider = _FakeProvider()
    targets = [{"key": "title:Acme", "kind": "experience", "company": "Acme", "current": "Backend Developer"}]
    suggest_title_changes(provider, targets, "posting", {}, "Data Scientist")
    return provider.last_prompt


@pytest.mark.gap_analysis
def test_prompt_has_three_steps_in_order():
    prompt = _prompt()

    markers = ["STEP 1 - THE CORE OF THE TARGET ROLE", "STEP 2 - WHICH ROLES THE CANDIDATE REALLY HELD", "STEP 3 - BUILD THE TITLE"]
    positions = [prompt.index(marker) for marker in markers]

    assert positions == sorted(positions)


@pytest.mark.gap_analysis
def test_target_is_reduced_to_the_words_a_recruiter_searches():
    prompt = _prompt()

    assert "Drop seniority" in prompt
    assert "programming languages, tools and technologies" in prompt
    assert '"Golang Backend Engineer, Financial Product Fraud" becomes "Backend Engineer"' in prompt


@pytest.mark.gap_analysis
def test_secondary_and_broader_roles_are_allowed():
    prompt = _prompt()

    assert "It does not have to be the main part." in prompt
    assert "broader name of the candidate's own role" in prompt
    assert "joined with \" & \" or \"/\"" in prompt


@pytest.mark.gap_analysis
def test_goal_is_maximum_overlap_with_the_target_and_an_exact_copy_when_possible():
    prompt = _prompt()

    assert "as many words as possible" in prompt
    assert "exact copy of the core of the target role" in prompt


@pytest.mark.gap_analysis
def test_own_identity_is_always_kept():
    prompt = _prompt()

    assert "Always keep at least a hint of the candidate's own role and identity" in prompt


@pytest.mark.gap_analysis
def test_other_professions_go_into_parentheses_without_the_role_noun():
    prompt = _prompt()

    assert "in parentheses" in prompt
    assert "never using the role noun itself" in prompt
    assert "a product or project manager" in prompt


@pytest.mark.gap_analysis
def test_technology_names_need_support_in_the_work_text():
    prompt = _prompt()

    assert "only if the work text names that same thing" in prompt
    assert "Never add or raise seniority" in prompt


@pytest.mark.gap_analysis
def test_specific_and_broad_variants_of_the_target_are_offered():
    prompt = _prompt()

    assert "specific variant" in prompt
    assert "broad variant" in prompt
    assert '"Software Engineer, Backend" gives the specific variant "Backend Engineer"' in prompt


@pytest.mark.gap_analysis
def test_exact_copy_case_is_limited_to_an_exact_match_of_the_own_role():
    prompt = _prompt()

    assert "This case applies only to an exact match of the candidate's own role." in prompt
    assert "use case b and never case a" in prompt


@pytest.mark.gap_analysis
def test_main_specialization_stays_in_every_title():
    prompt = _prompt()

    assert "stays in every new title" in prompt
    assert "Never remove the main specialization" in prompt


@pytest.mark.gap_analysis
def test_prompt_is_not_tied_to_one_profession():
    prompt = _prompt()

    for word in ["LLM", "GenAI", "Generative", "Agentic", "FAMILY"]:
        assert word not in prompt