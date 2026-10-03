import pytest

from core.automation import pipeline, stages


@pytest.mark.automation
def test_blocked_job_is_archived_even_with_high_score():
    assert pipeline._decide_stage(10, 6, 3, blocked=True) == stages.ARCHIVED_AUTO


@pytest.mark.automation
def test_blocked_job_without_score_is_archived():
    assert pipeline._decide_stage(None, 6, 3, blocked=True) == stages.ARCHIVED_AUTO


@pytest.mark.automation
def test_unblocked_job_follows_thresholds():
    assert pipeline._decide_stage(8, 6, 3, blocked=False) == stages.PASSED
    assert pipeline._decide_stage(2, 6, 3, blocked=False) == stages.ARCHIVED_AUTO
    assert pipeline._decide_stage(5, 6, 3) == stages.NEEDS_REVIEW