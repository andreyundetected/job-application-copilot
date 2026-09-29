import pytest

import config
from core.evaluator.pipeline import evaluate_job_posting, quick_extract_job_posting


class _CapturingProvider:
    def __init__(self):
        self.kwargs = None

    def call(self, system_prompt, user_prompt, **kwargs):
        self.kwargs = kwargs
        return "<score>5</score>"


@pytest.mark.evaluator
def test_evaluator_passes_configured_temperature(monkeypatch):
    monkeypatch.setattr(config, "EVALUATOR_TEMPERATURE", 0.0)
    provider = _CapturingProvider()

    evaluate_job_posting(provider, "job", "resume", "linkedin", [])

    assert provider.kwargs["temperature"] == 0.0


@pytest.mark.evaluator
def test_quick_extract_passes_configured_temperature(monkeypatch):
    monkeypatch.setattr(config, "EVALUATOR_TEMPERATURE", 0.0)
    provider = _CapturingProvider()

    quick_extract_job_posting(provider, "job")

    assert provider.kwargs["temperature"] == 0.0


@pytest.mark.evaluator
def test_empty_setting_sends_no_temperature_value(monkeypatch):
    monkeypatch.setattr(config, "EVALUATOR_TEMPERATURE", None)
    provider = _CapturingProvider()

    evaluate_job_posting(provider, "job", "resume", "linkedin", [])

    assert provider.kwargs["temperature"] is None