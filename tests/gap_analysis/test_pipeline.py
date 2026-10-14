import pytest

from core.gap_analysis.pipeline import run_full_gap_analysis


class _SequenceProvider:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def call(self, system_prompt, user_prompt, max_tokens=None, **kwargs):
        self.calls += 1
        return self.responses.pop(0)


@pytest.mark.gap_analysis
def test_run_full_gap_analysis_extracts_then_classifies(monkeypatch):
    monkeypatch.setattr(
        "core.parsing.html_blocks.body_block_texts",
        lambda html, blocks: [{"field_path": "skills", "kind": "skills", "label": "Skills", "text": "Python"}],
    )
    monkeypatch.setattr("core.parsing.html_to_text.html_to_text", lambda html: "Python")
    provider = _SequenceProvider(
        [
            '<kw text="Python" tier="P0" kind="skill" level="required" />'
            '<kw text="Rust" tier="P0" kind="skill" level="required" />',
            '<k i="0" why="no source mentions it" bucket="unknown" />',
        ]
    )

    result = run_full_gap_analysis(provider, "job text", "<p>Python</p>", "", None)

    assert provider.calls == 2
    assert {item["text"]: item["status"] for item in result["gap_items"]} == {
        "Python": "exact",
        "Rust": "unknown",
    }
    assert result["resume_items"] == []