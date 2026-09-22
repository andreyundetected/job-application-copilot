import pytest

from core.discovery import ats


@pytest.mark.discovery
def test_all_registered_extractors_have_required_attributes():
    extractors = ats.all_extractors()
    assert len(extractors) >= 10

    for extractor in extractors:
        assert extractor.name
        assert extractor.site_filter_domains
        assert extractor.url_pattern is not None


@pytest.mark.discovery
def test_all_extractor_names_are_unique():
    names = [extractor.name for extractor in ats.all_extractors()]
    assert len(names) == len(set(names))


@pytest.mark.discovery
def test_default_target_sites_includes_every_extractor_domain():
    sites = ats.default_target_sites()
    for extractor in ats.all_extractors():
        for domain in extractor.site_filter_domains:
            assert domain in sites


@pytest.mark.discovery
def test_detect_platform_dispatches_to_correct_extractor():
    assert ats.detect_platform("https://boards.greenhouse.io/example/jobs/123") == "greenhouse"
    assert ats.detect_platform("https://jobs.lever.co/example/abc") == "lever"
    assert ats.detect_platform("https://example.bamboohr.com/careers/42") == "bamboohr"
    assert ats.detect_platform("https://example.teamtailor.com/jobs/123-role") == "teamtailor"
    assert ats.detect_platform("https://example.com/careers/123") is None