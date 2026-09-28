import pytest

from core.parsing.html_blocks import (
    block_fragments,
    clean_transient_attrs,
    normalize_elements,
    replace_block_elements,
    split_top_level,
)


@pytest.mark.parsing
def test_split_top_level_keeps_nested_lists_whole():
    html = '<p data-eid="e1">Title</p><ul data-eid="e2"><li>One</li><li>Two</li></ul>'

    elements = split_top_level(html)

    assert [e["tag"] for e in elements] == ["p", "ul"]
    assert elements[1]["eid"] == "e2"
    assert elements[1]["html"].count("<li>") == 2


@pytest.mark.parsing
def test_split_top_level_wraps_stray_text():
    elements = split_top_level('<p data-eid="e1">A</p>stray text')

    assert len(elements) == 2
    assert elements[1]["html"] == "<p>stray text</p>"


@pytest.mark.parsing
def test_normalize_assigns_missing_ids_and_rebuilds_blocks():
    html = '<p data-eid="e1">A</p><p>B</p><p data-eid="e3">C</p>'
    blocks = [{"id": "b1", "kind": "summary", "element_ids": ["e1", "e3"]}]

    new_html, new_blocks = normalize_elements(html, blocks)

    elements = split_top_level(new_html)
    assert all(e["eid"] for e in elements)
    assert len({e["eid"] for e in elements}) == 3
    assert new_blocks[0]["element_ids"] == ["e1", elements[1]["eid"], "e3"] or new_blocks[0]["element_ids"] == ["e1", "e3"]


@pytest.mark.parsing
def test_normalize_duplicate_id_adopts_previous_block():
    html = '<p data-eid="e1">A</p><p data-eid="e1">A2</p>'
    blocks = [{"id": "b1", "kind": "summary", "element_ids": ["e1"]}]

    new_html, new_blocks = normalize_elements(html, blocks)

    elements = split_top_level(new_html)
    assert elements[0]["eid"] != elements[1]["eid"]
    assert len(new_blocks[0]["element_ids"]) == 2


@pytest.mark.parsing
def test_normalize_drops_blocks_without_elements():
    html = '<p data-eid="e1">A</p>'
    blocks = [{"id": "b1", "kind": "summary", "element_ids": ["gone"]}]

    _, new_blocks = normalize_elements(html, blocks)

    assert new_blocks == []


@pytest.mark.parsing
def test_replace_block_elements_keeps_ids_by_position():
    html = '<p data-eid="e1">Title</p>\n<p data-eid="e2">Old</p>\n<p data-eid="e3">Tail</p>'
    block = {"id": "b1", "kind": "summary", "element_ids": ["e2"]}

    new_html, new_block = replace_block_elements(html, block, ["<p>New</p>"])

    assert new_block["element_ids"] == ["e2"]
    assert block_fragments(new_html, new_block) == ['<p data-eid="e2">New</p>']
    assert "Title" in new_html and "Tail" in new_html


@pytest.mark.parsing
def test_clean_transient_attrs_removes_only_block_markers():
    html = '<p class="blk-mapped blk-hot keep" data-blk="summary" data-eid="e1">A</p>'

    assert clean_transient_attrs(html) == '<p class="keep" data-eid="e1">A</p>'