import pytest

from core.structuring.pipeline import structure_resume_text, structure_linkedin_text


class _FakeProvider:
    def __init__(self, response_text: str):
        self.response_text = response_text
        self.last_user_prompt = None

    def call(self, system_prompt: str, user_prompt: str) -> str:
        self.last_user_prompt = user_prompt
        return self.response_text


_SAMPLE_RESPONSE = """
<name>Sample Name | Software Engineer</name>
<contact>City, Country</contact>
<contact>sample@example.com</contact>
<summary>Sample summary text.</summary>
<experience company="Example Corp" role="Software Engineer" location="Remote" dates="2023-2025" employment_type="full-time">
<description>Sample company description</description>
<bullet>Sample bullet one</bullet>
<bullet>Sample bullet two</bullet>
<subsection heading="Sample project">
<bullet>Sample subsection bullet</bullet>
</subsection>
</experience>
<extra_section heading="INDEPENDENT PROJECTS">
<text>Sample independent projects text</text>
</extra_section>
<skill_group label="Languages">
<item>Python</item>
<item>SQL</item>
</skill_group>
"""


@pytest.mark.structuring
def test_structure_resume_text_maps_all_fields():
    provider = _FakeProvider(_SAMPLE_RESPONSE)

    content = structure_resume_text(provider, "raw resume text")

    assert content["name"] == "Sample Name | Software Engineer"
    assert content["contacts"] == ["City, Country", "sample@example.com"]
    assert content["summary"] == "Sample summary text."

    experience = content["experience"][0]
    assert experience["company"] == "Example Corp"
    assert experience["role"] == "Software Engineer"
    assert experience["bullets"] == ["Sample bullet one", "Sample bullet two"]
    assert experience["subsections"][0]["heading"] == "Sample project"
    assert experience["subsections"][0]["bullets"] == ["Sample subsection bullet"]

    assert content["extra_sections"][0]["heading"] == "INDEPENDENT PROJECTS"
    assert content["extra_sections"][0]["text"] == "Sample independent projects text"

    assert content["skills"][0]["label"] == "Languages"
    assert content["skills"][0]["items"] == ["Python", "SQL"]


@pytest.mark.structuring
def test_structure_resume_text_handles_missing_optional_sections():
    provider = _FakeProvider("<name>Only Name</name>")

    content = structure_resume_text(provider, "raw resume text")

    assert content["name"] == "Only Name"
    assert content["contacts"] == []
    assert content["summary"] is None
    assert content["experience"] == []
    assert content["extra_sections"] == []
    assert content["skills"] == []


@pytest.mark.structuring
def test_structure_linkedin_text_uses_linkedin_label_in_prompt():
    provider = _FakeProvider(_SAMPLE_RESPONSE)

    structure_linkedin_text(provider, "raw linkedin text")

    assert "LinkedIn experience export" in provider.last_user_prompt
    assert "raw linkedin text" in provider.last_user_prompt


@pytest.mark.structuring
def test_structure_resume_text_handles_experience_without_subsections():
    response = """
    <experience company="Solo Corp" role="Engineer" location="Remote" dates="2020-2021" employment_type="full-time">
    <bullet>Sample bullet</bullet>
    </experience>
    """
    provider = _FakeProvider(response)

    content = structure_resume_text(provider, "raw text")

    experience = content["experience"][0]
    assert experience["subsections"] == []
    assert experience["description"] is None