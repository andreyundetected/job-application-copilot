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
<block type="paragraph">Sample company description</block>
<block type="heading">Sample project</block>
<block type="bullet_list">
<item>Sample bullet one</item>
<item>Sample bullet two</item>
</block>
</experience>
<extra_section heading="INDEPENDENT PROJECTS">
<block type="paragraph">Sample independent projects text</block>
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
    assert experience["content"][0] == {"type": "paragraph", "text": "Sample company description"}
    assert experience["content"][1] == {"type": "heading", "text": "Sample project"}
    assert experience["content"][2] == {
        "type": "bullet_list",
        "items": ["Sample bullet one", "Sample bullet two"],
    }

    assert content["extra_sections"][0]["heading"] == "INDEPENDENT PROJECTS"
    assert content["extra_sections"][0]["content"][0]["text"] == "Sample independent projects text"

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
def test_structure_resume_text_handles_multiple_projects_under_one_role():
    response = """
    <experience company="Solo Corp" role="Engineer" location="Remote" dates="2020-2021" employment_type="full-time">
    <block type="paragraph">Intro paragraph</block>
    <block type="heading">Project One</block>
    <block type="bullet_list">
    <item>Bullet for project one</item>
    </block>
    <block type="heading">Project Two</block>
    <block type="bullet_list">
    <item>Bullet for project two</item>
    </block>
    </experience>
    """
    provider = _FakeProvider(response)

    content = structure_resume_text(provider, "raw text")

    experience = content["experience"][0]
    assert len(experience["content"]) == 5
    assert experience["content"][1] == {"type": "heading", "text": "Project One"}
    assert experience["content"][3] == {"type": "heading", "text": "Project Two"}