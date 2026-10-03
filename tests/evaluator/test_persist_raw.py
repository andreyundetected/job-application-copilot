import pytest

from core.evaluator.persist import build_checked_keywords

_QUICK = {"location": "Berlin", "work_mode": "remote", "salary": {}, "summary": "Short."}
_RESULT = {"matched_factors": [], "raw_response": "raw model text"}


@pytest.mark.evaluator
def test_checked_keywords_store_raw_response_and_prompt_hash():
    checked = build_checked_keywords(_QUICK, _RESULT)

    assert checked["raw_response"] == "raw model text"
    assert len(checked["prompt_hash"]) == 10


@pytest.mark.evaluator
def test_checked_keywords_tolerate_missing_raw_response():
    checked = build_checked_keywords(_QUICK, {"matched_factors": []})

    assert checked["raw_response"] is None