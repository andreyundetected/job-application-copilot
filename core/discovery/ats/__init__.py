import importlib
import inspect
import logging
import pkgutil

import requests

from core.discovery.ats.base import BaseATSExtractor

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, BaseATSExtractor] = {}


def _discover() -> None:
    for _, module_name, _ in pkgutil.iter_modules(__path__):
        if module_name == "base":
            continue
        module = importlib.import_module(f"{__name__}.{module_name}")
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if issubclass(obj, BaseATSExtractor) and obj is not BaseATSExtractor and obj.__module__ == module.__name__:
                instance = obj()
                _REGISTRY[instance.name] = instance


_discover()


def all_extractors() -> list[BaseATSExtractor]:
    return list(_REGISTRY.values())


def default_target_sites() -> list[str]:
    """Every site_filter_domains entry from every registered extractor, in
    registration order - used to build the automation search query pool and
    the "Boards to reference" chips in the UI. Adding a new ATS file adds its
    domain(s) here automatically."""
    sites: list[str] = []
    for extractor in _REGISTRY.values():
        sites.extend(extractor.site_filter_domains)
    return sites


def detect_platform(url: str) -> str | None:
    for extractor in _REGISTRY.values():
        if extractor.matches(url):
            return extractor.name
    return None


def _is_known_ats_domain(url: str) -> bool:
    all_domains = tuple(domain for extractor in _REGISTRY.values() for domain in extractor.site_filter_domains)
    return any(domain in url for domain in all_domains)


def extract_job_text(url: str) -> str | None:
    platform = detect_platform(url)
    if platform is None:
        if _is_known_ats_domain(url):
            logger.info(
                "extract_job_text: url=%s is on a known ATS domain but isn't a single job-posting link "
                "(likely a company board root/listing page, not an indexable job) - skipping",
                url,
            )
        else:
            logger.warning("extract_job_text: no ATS extractor for url=%s (domain not supported)", url)
        return None

    extractor = _REGISTRY[platform]
    try:
        result = extractor.extract(url)
        if result is None:
            logger.warning(
                "extract_job_text: %s extractor could not get job text for url=%s (see specific reason logged above)",
                platform, url,
            )
        else:
            logger.info("extract_job_text: %s extractor got %s chars for url=%s", platform, len(result), url)
        return result
    except requests.RequestException as error:
        logger.error("extract_job_text: network error for url=%s: %s", url, error)
        return None
    except (ValueError, KeyError, TypeError) as error:
        logger.error("extract_job_text: parse error for url=%s: %s", url, error)
        return None