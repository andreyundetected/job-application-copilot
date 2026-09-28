import pytest

from core.gap_analysis.block_generation import (
    build_units,
    generate_block_fragments,
    merge_generated,
    parse_generated,
    rebuild_paragraph,
)


class _FakeProvider:
    def __init__(self, response_text: str):
        self.response_text = response_text

    def call(self, system_prompt, user_prompt, max_tokens=None, reasoning_effort=None):
        return self.response_text


_FRAGMENTS = [
    '<p data-eid="e1"><span style="font-size:10pt">Old text here today</span></p>',
    '<ul data-eid="e2"><li><span style="font-size:10pt">One</span></li></ul>',
]


@pytest.mark.gap_analysis
def test_merge_keeps_unchanged_units_and_preserves_style_of_changed():
    units = build_units(_FRAGMENTS)
    parsed = parse_generated('<el n="0">New text here today</el><el n="1" list="true"><li>One</li></el>')

    merged = merge_generated(_FRAGMENTS, units, parsed)

    assert "New text here today" in merged[0]
    assert 'font-size:10pt' in merged[0]
    assert 'data-eid="e1"' in merged[0]
    assert merged[1] == _FRAGMENTS[1]


@pytest.mark.gap_analysis
def test_rebuild_paragraph_escapes_text():
    result = rebuild_paragraph(_FRAGMENTS[0], "A <b> & B")

    assert "A &lt;b&gt; &amp; B" in result


@pytest.mark.gap_analysis
def test_generate_block_fragments_rejects_large_length_change():
    provider = _FakeProvider('<el n="0">' + "word " * 200 + '</el><el n="1" list="true"><li>One</li></el>')

    with pytest.raises(ValueError):
        generate_block_fragments(provider, _FRAGMENTS, "Summary", "resume", "job", [], [], "")


@pytest.mark.gap_analysis
def test_generate_block_fragments_returns_original_when_nothing_parsed():
    provider = _FakeProvider("no tags at all")

    result = generate_block_fragments(provider, _FRAGMENTS, "Summary", "resume", "job", [], [], "")

    assert result == _FRAGMENTS