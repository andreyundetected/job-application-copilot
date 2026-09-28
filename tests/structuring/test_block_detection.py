import pytest

from core.structuring.block_detection import detect_blocks, finalize_blocks, parse_blocks


class _FakeProvider:
    def __init__(self, response_text: str):
        self.response_text = response_text

    def call(self, system_prompt, user_prompt, max_tokens=None, reasoning_effort=None):
        return self.response_text


_HTML = (
    '<p data-eid="e1">Sample Name</p>'
    '<p data-eid="e2">SUMMARY</p>'
    '<p data-eid="e3">Summary text</p>'
    '<p data-eid="e4">Example Corp - Engineer</p>'
    '<ul data-eid="e5"><li>Built things</li></ul>'
)


@pytest.mark.structuring
def test_detect_blocks_builds_field_paths_and_skips_headings():
    raw = (
        '<block kind="title_main" from="e1" to="e1" />'
        '<block kind="summary" from="e3" to="e3" />'
        '<block kind="exp_title" company="Example Corp" role="Engineer" from="e4" to="e4" />'
        '<block kind="exp_body" company="Example Corp" from="e5" to="e5" />'
    )

    blocks = detect_blocks(_FakeProvider(raw), _HTML)

    assert [b["field_path"] for b in blocks] == [
        "title:main",
        "summary",
        "title:Example Corp",
        "experience: Example Corp",
    ]
    assert all("e2" not in b["element_ids"] for b in blocks)
    assert blocks[2]["role"] == "Engineer"


@pytest.mark.structuring
def test_parse_blocks_drops_overlaps_and_unknown_ids():
    raw = (
        '<block kind="summary" from="e1" to="e2" />'
        '<block kind="skills" from="e2" to="e3" />'
        '<block kind="skills" from="zz" to="e3" />'
        '<block kind="bogus" from="e3" to="e3" />'
    )

    blocks = parse_blocks(raw, ["e1", "e2", "e3"])

    assert len(blocks) == 1
    assert blocks[0]["element_ids"] == ["e1", "e2"]


@pytest.mark.structuring
def test_finalize_blocks_makes_field_paths_unique():
    blocks = finalize_blocks(
        [
            {"id": "a", "kind": "exp_body", "company": "Acme", "element_ids": ["e1"]},
            {"id": "b", "kind": "exp_body", "company": "Acme", "element_ids": ["e2"]},
        ]
    )

    assert blocks[0]["field_path"] == "experience: Acme"
    assert blocks[1]["field_path"] == "experience: Acme #2"