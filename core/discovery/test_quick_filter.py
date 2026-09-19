import pytest

from core.discovery.quick_filter import quick_filter_search_results, render_quick_filter_prompt


class _FakeProvider:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.last_user_prompt = None

    def call(self, system_prompt: str, user_prompt: str) -> str:
        self.last_user_prompt = user_prompt
        return self.response_text


_SAMPLE_RESULTS = [
    {
        "id": 1,
        "title": "Senior AI Engineer",
        "snippet": "Build LLM pipelines",
        "url": "https://boards.greenhouse.io/a/jobs/1",
    },
    {
        "id": 2,
        "title": "Warehouse Associate",
        "snippet": "Pack boxes",
        "url": "https://jobs.lever.co/b/2",
    },
]


@pytest.mark.discovery
def test_quick_filter_parses_verdicts():
    provider = _FakeProvider('<verdict id="1">proceed</verdict><verdict id="2">skip</verdict>')

    verdicts = quick_filter_search_results(
        provider,
        _SAMPLE_RESULTS,
        resume_text="resume",
        linkedin_text="linkedin",
        blockers=[],
    )

    assert verdicts == {1: "proceed", 2: "skip"}


@pytest.mark.discovery
def test_quick_filter_defaults_missing_id_to_proceed():
    provider = _FakeProvider('<verdict id="1">skip</verdict>')

    verdicts = quick_filter_search_results(
        provider,
        _SAMPLE_RESULTS,
        resume_text="resume",
        linkedin_text="linkedin",
        blockers=[],
    )

    assert verdicts[1] == "skip"
    assert verdicts[2] == "proceed"


@pytest.mark.discovery
def test_quick_filter_defaults_invalid_verdict_text_to_proceed():
    provider = _FakeProvider('<verdict id="1">maybe</verdict><verdict id="2">skip</verdict>')

    verdicts = quick_filter_search_results(
        provider,
        _SAMPLE_RESULTS,
        resume_text="resume",
        linkedin_text="linkedin",
        blockers=[],
    )

    assert verdicts[1] == "proceed"
    assert verdicts[2] == "skip"


@pytest.mark.discovery
def test_quick_filter_returns_empty_dict_for_no_results():
    provider = _FakeProvider("")

    verdicts = quick_filter_search_results(
        provider, [], resume_text="resume", linkedin_text="linkedin", blockers=[]
    )

    assert verdicts == {}


@pytest.mark.discovery
def test_quick_filter_passes_blockers_and_results_to_prompt():
    provider = _FakeProvider('<verdict id="1">proceed</verdict><verdict id="2">skip</verdict>')

    quick_filter_search_results(
        provider,
        _SAMPLE_RESULTS,
        resume_text="resume",
        linkedin_text="linkedin",
        blockers=["Requires a university degree"],
    )

    assert "Requires a university degree" in provider.last_user_prompt
    assert "Senior AI Engineer" in provider.last_user_prompt
    assert "Warehouse Associate" in provider.last_user_prompt


@pytest.mark.discovery
def test_render_quick_filter_prompt_includes_extra_info_when_given():
    prompt = render_quick_filter_prompt(
        _SAMPLE_RESULTS,
        resume_text="resume",
        linkedin_text="linkedin",
        blockers=[],
        extra_info="Sample extra context.",
    )

    assert "Sample extra context." in prompt


@pytest.mark.discovery
def test_render_quick_filter_prompt_omits_extra_info_section_when_not_given():
    prompt = render_quick_filter_prompt(
        _SAMPLE_RESULTS, resume_text="resume", linkedin_text="linkedin", blockers=[]
    )

    assert "ADDITIONAL CONTEXT ABOUT THE CANDIDATE" not in prompt