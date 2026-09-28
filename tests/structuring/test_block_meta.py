import pytest

from core.structuring.block_detection import detect_blocks, parse_blocks


class _FakeProvider:
    def __init__(self, response_text: str):
        self.response_text = response_text

    def call(self, system_prompt, user_prompt, max_tokens=None, reasoning_effort=None):
        return self.response_text


@pytest.mark.structuring
def test_parse_blocks_merges_adjacent_bodies_of_one_company():
    raw = (
        '<block kind="exp_body" company="Acme" from="e1" to="e1" />'
        '<block kind="exp_body" company="Acme" from="e2" to="e3" />'
        '<block kind="exp_body" company="Other" from="e4" to="e4" />'
    )

    blocks = parse_blocks(raw, ["e1", "e2", "e3", "e4"])

    assert len(blocks) == 2
    assert blocks[0]["element_ids"] == ["e1", "e2", "e3"]
    assert blocks[0]["field_path"] == "experience: Acme"


@pytest.mark.structuring
def test_parse_blocks_does_not_merge_across_a_gap():
    raw = (
        '<block kind="exp_body" company="Acme" from="e1" to="e1" />'
        '<block kind="exp_body" company="Acme" from="e3" to="e3" />'
    )

    blocks = parse_blocks(raw, ["e1", "e2", "e3"])

    assert len(blocks) == 2
    assert blocks[1]["field_path"] == "experience: Acme #2"


@pytest.mark.structuring
def test_independent_projects_become_experience_body_without_title():
    html = '<p data-eid="e1">INDEPENDENT PROJECTS</p><p data-eid="e2">Project one</p><ul data-eid="e3"><li>Built a bot</li></ul>'
    raw = '<block kind="exp_body" company="Independent Projects" from="e2" to="e3" />'

    blocks = detect_blocks(_FakeProvider(raw), html)

    assert blocks[0]["field_path"] == "experience: Independent Projects"
    assert blocks[0]["label"] == "Independent Projects"