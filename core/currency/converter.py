import logging
import time

import requests

logger = logging.getLogger(__name__)

FRANKFURTER_BASE_URL = "https://api.frankfurter.app/latest"

_RATE_CACHE_TTL_SECONDS = 6 * 60 * 60
_rate_cache: dict[str, tuple[float, dict[str, float]]] = {}

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


def _fetch_rates(base_currency: str) -> dict[str, float]:
    cached = _rate_cache.get(base_currency)
    if cached is not None and time.time() - cached[0] < _RATE_CACHE_TTL_SECONDS:
        return cached[1]

    try:
        response = requests.get(FRANKFURTER_BASE_URL, params={"from": base_currency}, timeout=10)
        response.raise_for_status()
        data = response.json()
        rates = dict(data.get("rates") or {})
        rates[base_currency] = 1.0
    except (requests.RequestException, ValueError) as error:
        logger.warning("Currency rate fetch failed for base=%s: %s", base_currency, error)
        if cached is not None:
            return cached[1]
        raise CurrencyConversionError(f"Could not fetch exchange rates for {base_currency}") from error

    _rate_cache[base_currency] = (time.time(), rates)
    return rates


def convert_amount(amount: float, from_currency: str, to_currency: str) -> float:
    from_currency = (from_currency or "USD").upper()
    to_currency = (to_currency or "USD").upper()

    if from_currency == to_currency:
        return amount

    rates = _fetch_rates(from_currency)
    rate = rates.get(to_currency)
    if rate is None:
        raise CurrencyConversionError(f"No exchange rate from {from_currency} to {to_currency}")

    return amount * rate


def convert_period(amount: float, from_period: str, to_period: str) -> float:
    from_hours = _PERIOD_TO_HOURS.get(from_period, HOURS_PER_YEAR)
    to_hours = _PERIOD_TO_HOURS.get(to_period, HOURS_PER_YEAR)
    return (amount / from_hours) * to_hours


def convert_salary(amount: float, from_currency: str, from_period: str, to_currency: str, to_period: str) -> float:
    converted = convert_amount(amount, from_currency, to_currency)
    return convert_period(converted, from_period, to_period)