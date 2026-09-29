import pytest

from core.discovery import poll_cycle, run_control


class _Company:
    def __init__(self, company_id, ats_name):
        self.id = company_id
        self.ats_name = ats_name
        self.slug = f"slug-{company_id}"


class _FakeSession:
    def close(self):
        pass


@pytest.fixture()
def fake_env(monkeypatch):
    companies = [_Company(1, "a"), _Company(2, "b"), _Company(3, "a"), _Company(4, "b"), _Company(5, "a")]
    monkeypatch.setattr(poll_cycle, "DiscoverySessionLocal", lambda: _FakeSession())
    monkeypatch.setattr(poll_cycle.discovery_crud, "list_ranked_live_companies", lambda session: companies)
    run_control.reset_run()
    return companies


@pytest.mark.discovery
def test_full_scan_checks_all_companies_in_rank_order_in_one_pass(monkeypatch, fake_env):
    batches = []

    def fake_run_batch(batch):
        batches.append([item[0] for item in batch])
        for _ in batch:
            run_control.note_company_checked()
        return []

    monkeypatch.setattr(poll_cycle, "_run_batch", fake_run_batch)

    poll_cycle.run_full_scan()

    assert batches == [[1, 2, 3, 4, 5]]

    stats = run_control.get_stats()
    assert stats["phase"] == "full_scan"
    assert stats["full_scan_total"] == 5
    assert stats["full_scan_checked"] == 5
    assert stats["full_scan_done"] is True


@pytest.mark.discovery
def test_full_scan_not_marked_done_when_cancelled(monkeypatch, fake_env):
    def fake_run_batch(batch):
        run_control.cancel_run()
        return []

    monkeypatch.setattr(poll_cycle, "_run_batch", fake_run_batch)

    poll_cycle.run_full_scan()

    assert run_control.get_stats()["full_scan_done"] is False


@pytest.mark.discovery
def test_note_company_checked_counts_only_during_full_scan():
    run_control.reset_run()
    run_control.set_phase("listening")
    run_control.note_company_checked()

    assert run_control.get_stats()["full_scan_checked"] == 0

    run_control.set_phase("full_scan")
    run_control.note_company_checked()

    assert run_control.get_stats()["full_scan_checked"] == 1