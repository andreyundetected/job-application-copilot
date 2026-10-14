import pytest

from core.gap_analysis.block_generation import build_units, merge_generated, parse_generated


@pytest.mark.gap_analysis
def test_line_breaks_inside_a_paragraph_survive_a_rewrite():
    fragment = "<p>Languages: Python<br>Frameworks: Flask</p>"
    units = build_units([fragment])

    assert units[0]["text"] == "Languages: Python\nFrameworks: Flask"

    parsed = parse_generated('<el n="0">Languages: Python, SQL\nFrameworks: Flask</el>')
    merged = merge_generated([fragment], units, parsed)

    assert merged[0] == "<p>Languages: Python, SQL<br>Frameworks: Flask</p>"