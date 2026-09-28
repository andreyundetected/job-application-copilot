import pytest

from core.discovery.posting_batch import decide_batch_action


@pytest.mark.discovery
def test_idle_when_run_is_off_even_if_window_elapsed_and_queue_full():
    assert decide_batch_action(False, False, 9999, 60, 100, 25) == "idle"


@pytest.mark.discovery
def test_drain_once_when_run_just_turned_off_with_pending():
    assert decide_batch_action(False, True, 5, 60, 3, 25) == "drain"


@pytest.mark.discovery
def test_no_drain_when_run_just_turned_off_with_empty_queue():
    assert decide_batch_action(False, True, 5, 60, 0, 25) == "idle"


@pytest.mark.discovery
def test_start_resets_timer_when_run_turns_on():
    assert decide_batch_action(True, False, 9999, 60, 100, 25) == "start"


@pytest.mark.discovery
def test_flush_when_window_elapsed():
    assert decide_batch_action(True, True, 61, 60, 1, 25) == "flush"


@pytest.mark.discovery
def test_flush_when_force_size_reached_before_window():
    assert decide_batch_action(True, True, 5, 60, 25, 25) == "flush"


@pytest.mark.discovery
def test_wait_when_neither_condition_met():
    assert decide_batch_action(True, True, 5, 60, 3, 25) == "wait"


@pytest.mark.discovery
def test_force_size_zero_disables_size_trigger():
    assert decide_batch_action(True, True, 5, 60, 500, 0) == "wait"