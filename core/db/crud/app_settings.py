from sqlalchemy.orm import Session

from core.db.models import AppSettings


def get_app_settings(session: Session) -> AppSettings | None:
    return session.query(AppSettings).first()


def upsert_app_settings(
    session: Session,
    pregenerate_enabled: bool | None = None,
    pregenerate_min_score: int | None = None,
) -> AppSettings:
    settings_row = session.query(AppSettings).first()

    if settings_row is None:
        settings_row = AppSettings(
            pregenerate_enabled=pregenerate_enabled if pregenerate_enabled is not None else False,
            pregenerate_min_score=pregenerate_min_score if pregenerate_min_score is not None else 7,
        )
        session.add(settings_row)
    else:
        if pregenerate_enabled is not None:
            settings_row.pregenerate_enabled = pregenerate_enabled
        if pregenerate_min_score is not None:
            settings_row.pregenerate_min_score = pregenerate_min_score

    session.commit()
    session.refresh(settings_row)
    return settings_row