import json

import pytest
import requests

from core.currency import converter


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(converter, "CACHE_FILE", tmp_path / "rates.json")
    monkeypatch.setattr(converter, "_memory", None)
    monkeypatch.setattr(converter, "_failed_at", None)


def test_falls_back_to_next_source_and_cross_converts(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        if "frankfurter" in url:
            raise requests.ConnectTimeout("timeout")
        return _Response({"result": "success", "rates": {"EUR": 0.5, "GBP": 0.25}})

    monkeypatch.setattr(converter.requests, "get", fake_get)

    assert converter.convert_amount(100, "GBP", "EUR") == 200
    assert len(calls) == 2


def test_failure_is_not_retried_during_cooldown(monkeypatch):
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        raise requests.ConnectTimeout("timeout")

    monkeypatch.setattr(converter.requests, "get", fake_get)

    for _ in range(4):
        with pytest.raises(converter.CurrencyConversionError):
            converter.convert_amount(100, "USD", "EUR")

    assert len(calls) == 3


def test_uses_stale_disk_cache_when_all_sources_fail(monkeypatch):
    converter.CACHE_FILE.write_text(
        json.dumps({"fetched_at": 0, "rates": {"USD": 1.0, "EUR": 0.5}}), encoding="utf-8"
    )

    def fake_get(url, params=None, timeout=None):
        raise requests.ConnectTimeout("timeout")

    monkeypatch.setattr(converter.requests, "get", fake_get)

    assert converter.convert_amount(10, "USD", "EUR") == 5


def test_success_is_saved_to_disk(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        return _Response({"rates": {"EUR": 0.5}})

    monkeypatch.setattr(converter.requests, "get", fake_get)

    converter.convert_amount(10, "USD", "EUR")

    saved = json.loads(converter.CACHE_FILE.read_text(encoding="utf-8"))
    assert saved["rates"]["EUR"] == 0.5


def test_convert_salary_changes_currency_and_period(monkeypatch):
    def fake_get(url, params=None, timeout=None):
        return _Response({"rates": {"EUR": 2.0, "GBP": 1.0}})

    monkeypatch.setattr(converter.requests, "get", fake_get)

    monthly_eur = converter.convert_salary(1920, "GBP", "year", "EUR", "month")

    assert monthly_eur == pytest.approx(1920 * 2.0 / 12)