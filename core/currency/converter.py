import json
import logging
import threading
import time

import requests

import config

logger = logging.getLogger(__name__)

_RATE_TTL_SECONDS = 6 * 60 * 60
_FAILURE_COOLDOWN_SECONDS = 2 * 60
_REQUEST_TIMEOUT_SECONDS = 4

CACHE_FILE = config.DATA_DIR / "rates_cache.json"

HOURS_PER_MONTH = 160
MONTHS_PER_YEAR = 12
HOURS_PER_YEAR = HOURS_PER_MONTH * MONTHS_PER_YEAR

_PERIOD_TO_HOURS = {"hour": 1, "month": HOURS_PER_MONTH, "year": HOURS_PER_YEAR}

SUPPORTED_CURRENCIES = [
    "USD", "EUR", "GBP", "CHF", "PLN", "CZK", "UAH", "TRY", "ILS",
    "AED", "INR", "CNY", "JPY", "CAD", "AUD", "SGD", "SEK", "NOK", "DKK",
    "MXN", "BRL", "RSD", "GEL", "KZT",
]


class CurrencyConversionError(Exception):
    pass


def _parse_frankfurter(data):
    return data.get("rates")


def _parse_er_api(data):
    if data.get("result") != "success":
        raise ValueError("unsuccessful response")
    return data.get("rates")


def _parse_fawaz(data):
    return data.get("usd")


_SOURCES = [
    ("frankfurter", "https://api.frankfurter.dev/v1/latest", {"base": "USD"}, _parse_frankfurter),
    ("open.er-api", "https://open.er-api.com/v6/latest/USD", None, _parse_er_api),
    (
        "fawazahmed0",
        "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json",
        None,
        _parse_fawaz,
    ),
]

_lock = threading.Lock()
_memory: tuple[float, dict[str, float]] | None = None
_failed_at: float | None = None


def _normalize(raw) -> dict[str, float]:
    rates = {str(code).upper(): float(value) for code, value in (raw or {}).items() if value}
    if not rates:
        raise ValueError("no rates in response")
    rates["USD"] = 1.0
    return rates


def _load_disk() -> tuple[float, dict[str, float]] | None:
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        return float(data["fetched_at"]), {code: float(value) for code, value in data["rates"].items()}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def _save_disk(fetched_at: float, rates: dict[str, float]) -> None:
    try:
        CACHE_FILE.write_text(json.dumps({"fetched_at": fetched_at, "rates": rates}), encoding="utf-8")
    except OSError as error:
        logger.warning("Could not write currency rates cache: %s", error)


def _download_rates() -> dict[str, float]:
    last_error = None
    for name, url, params, parser in _SOURCES:
        try:
            response = requests.get(url, params=params, timeout=_REQUEST_TIMEOUT_SECONDS)
            response.raise_for_status()
            return _normalize(parser(response.json()))
        except (requests.RequestException, ValueError, TypeError, AttributeError) as error:
            logger.warning("Currency rate fetch failed via %s: %s", name, error)
            last_error = error
    raise CurrencyConversionError("Could not fetch exchange rates from any source") from last_error


def get_usd_rates() -> dict[str, float]:
    global _memory, _failed_at

    if _memory is None:
        _memory = _load_disk()

    now = time.time()
    if _memory is not None and now - _memory[0] < _RATE_TTL_SECONDS:
        return _memory[1]

    with _lock:
        now = time.time()
        if _memory is not None and now - _memory[0] < _RATE_TTL_SECONDS:
            return _memory[1]

        if _failed_at is not None and now - _failed_at < _FAILURE_COOLDOWN_SECONDS:
            if _memory is not None:
                return _memory[1]
            raise CurrencyConversionError("Exchange rates are temporarily unavailable")

        try:
            rates = _download_rates()
        except CurrencyConversionError:
            _failed_at = time.time()
            if _memory is not None:
                return _memory[1]
            raise

        _failed_at = None
        _memory = (time.time(), rates)
        _save_disk(*_memory)
        return rates


def warm_up_rates() -> None:
    try:
        get_usd_rates()
    except CurrencyConversionError as error:
        logger.warning("Currency rates warm-up failed: %s", error)


def convert_amount(amount: float, from_currency: str, to_currency: str) -> float:
    from_currency = (from_currency or "USD").upper()
    to_currency = (to_currency or "USD").upper()

    if from_currency == to_currency:
        return amount

    rates = get_usd_rates()
    from_rate = rates.get(from_currency)
    to_rate = rates.get(to_currency)
    if not from_rate or not to_rate:
        raise CurrencyConversionError(f"No exchange rate from {from_currency} to {to_currency}")

    return amount / from_rate * to_rate


def convert_period(amount: float, from_period: str, to_period: str) -> float:
    from_hours = _PERIOD_TO_HOURS.get(from_period, HOURS_PER_YEAR)
    to_hours = _PERIOD_TO_HOURS.get(to_period, HOURS_PER_YEAR)
    return (amount / from_hours) * to_hours


def convert_salary(amount: float, from_currency: str, from_period: str, to_currency: str, to_period: str) -> float:
    converted = convert_amount(amount, from_currency, to_currency)
    return convert_period(converted, from_period, to_period)