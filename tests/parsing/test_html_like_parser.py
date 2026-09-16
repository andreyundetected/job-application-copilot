import pytest

from core.parsing.html_like_parser import parse_html_like


@pytest.mark.parsing
def test_simple_repeated_tags_become_list():
    raw_text = """
    <a>answer one</a>
    <a>answer two</a>
    """

    result = parse_html_like(raw_text)

    assert result == {"a": ["answer one", "answer two"]}


@pytest.mark.parsing
def test_single_tag_still_becomes_list():
    raw_text = "<verdict>yes</verdict>"

    result = parse_html_like(raw_text)

    assert result == {"verdict": ["yes"]}


@pytest.mark.parsing
def test_empty_input_returns_empty_dict():
    result = parse_html_like("")

    assert result == {}


@pytest.mark.parsing
def test_attributes_are_strings_and_children_are_lists():
    raw_text = """
    <experience role="Backend Developer" company="Example Corp" dates="2023-2025">
    <bullet>Rebuilt the payments service</bullet>
    <bullet>Migrated legacy monolith</bullet>
    <skill>Python</skill>
    <skill>FastAPI</skill>
    </experience>
    """

    result = parse_html_like(raw_text)

    assert result == {
        "experience": [
            {
                "role": "Backend Developer",
                "company": "Example Corp",
                "dates": "2023-2025",
                "bullet": ["Rebuilt the payments service", "Migrated legacy monolith"],
                "skill": ["Python", "FastAPI"],
            }
        ]
    }


@pytest.mark.parsing
def test_multiple_blocks_with_same_tag_stay_isolated():
    raw_text = """
    <experience role="Backend Developer" company="Example Corp">
    <bullet>First job bullet</bullet>
    </experience>
    <experience role="LLM Engineer" company="Another Corp">
    <bullet>Second job bullet</bullet>
    </experience>
    """

    result = parse_html_like(raw_text)

    assert len(result["experience"]) == 2
    assert result["experience"][0]["role"] == "Backend Developer"
    assert result["experience"][0]["bullet"] == ["First job bullet"]
    assert result["experience"][1]["role"] == "LLM Engineer"
    assert result["experience"][1]["bullet"] == ["Second job bullet"]


@pytest.mark.parsing
def test_tag_with_attributes_and_text_content():
    raw_text = '<summary tone="professional">Experienced engineer with a strong track record.</summary>'

    result = parse_html_like(raw_text)

    assert result == {
        "summary": [
            {
                "tone": "professional",
                "text": "Experienced engineer with a strong track record.",
            }
        ]
    }


@pytest.mark.parsing
def test_nested_tags_without_attributes():
    raw_text = """
    <section>
    <heading>Skills</heading>
    <item>Python</item>
    <item>SQL</item>
    </section>
    """

    result = parse_html_like(raw_text)

    assert result == {
        "section": [
            {
                "heading": ["Skills"],
                "item": ["Python", "SQL"],
            }
        ]
    }


@pytest.mark.parsing
def test_whitespace_is_stripped_from_text():
    raw_text = """
    <a>
        answer with surrounding whitespace
    </a>
    """

    result = parse_html_like(raw_text)

    assert result == {"a": ["answer with surrounding whitespace"]}