from sqlalchemy.orm import Session

from core.db.models import AutomationSettings


def get_automation_settings(session: Session) -> AutomationSettings | None:
    return session.query(AutomationSettings).order_by(AutomationSettings.id.asc()).first()


def upsert_automation_settings(
    session: Session,
    min_score_to_proceed: int | None = None,
    max_score_to_archive: int | None = None,
    quick_filter_enabled: bool | None = None,
    auto_archive_enabled: bool | None = None,
    serpent_num_per_query: int | None = None,
    default_time_range: str | None = None,
    saved_queries: list | None = None,
    serpent_cost_per_request: float | None = None,
    catch_all_enabled: bool | None = None,
    max_pages_per_query: int | None = None,
) -> AutomationSettings:
    settings_row = session.query(AutomationSettings).first()

    if settings_row is None:
        settings_row = AutomationSettings(
            min_score_to_proceed=min_score_to_proceed if min_score_to_proceed is not None else 6,
            max_score_to_archive=max_score_to_archive if max_score_to_archive is not None else 3,
            quick_filter_enabled=quick_filter_enabled if quick_filter_enabled is not None else True,
            auto_archive_enabled=auto_archive_enabled if auto_archive_enabled is not None else False,
            serpent_num_per_query=serpent_num_per_query if serpent_num_per_query is not None else 100,
            default_time_range=default_time_range if default_time_range is not None else "w1",
            saved_queries=saved_queries or [],
            serpent_cost_per_request=serpent_cost_per_request,
            catch_all_enabled=catch_all_enabled if catch_all_enabled is not None else True,
            max_pages_per_query=max_pages_per_query if max_pages_per_query is not None else 10,
        )
        session.add(settings_row)
    else:
        if min_score_to_proceed is not None:
            settings_row.min_score_to_proceed = min_score_to_proceed
        if max_score_to_archive is not None:
            settings_row.max_score_to_archive = max_score_to_archive
        if quick_filter_enabled is not None:
            settings_row.quick_filter_enabled = quick_filter_enabled
        if auto_archive_enabled is not None:
            settings_row.auto_archive_enabled = auto_archive_enabled
        if serpent_num_per_query is not None:
            settings_row.serpent_num_per_query = serpent_num_per_query
        if default_time_range is not None:
            settings_row.default_time_range = default_time_range
        if saved_queries is not None:
            settings_row.saved_queries = saved_queries
        if serpent_cost_per_request is not None:
            settings_row.serpent_cost_per_request = serpent_cost_per_request
        if catch_all_enabled is not None:
            settings_row.catch_all_enabled = catch_all_enabled
        if max_pages_per_query is not None:
            settings_row.max_pages_per_query = max_pages_per_query

    session.commit()
    session.refresh(settings_row)
    return settings_row