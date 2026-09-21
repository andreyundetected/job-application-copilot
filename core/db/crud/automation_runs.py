import datetime

from sqlalchemy.orm import Session

from core.db.models import AutomationRun

_COUNTER_FIELDS = {
    "found_count",
    "quick_filtered_count",
    "scraped_count",
    "evaluated_count",
    "passed_count",
    "archived_count",
}


def create_automation_run(
    session: Session,
    queries_planned: list | None = None,
    max_results_override: int | None = None,
    max_queries_override: int | None = None,
) -> AutomationRun:
    run = AutomationRun(
        queries_planned=queries_planned,
        max_results_override=max_results_override,
        max_queries_override=max_queries_override,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def get_automation_run(session: Session, run_id: int) -> AutomationRun | None:
    return session.get(AutomationRun, run_id)


def list_automation_runs(session: Session, limit: int = 20) -> list[AutomationRun]:
    return (
        session.query(AutomationRun)
        .order_by(AutomationRun.created_at.desc())
        .limit(limit)
        .all()
    )


def mark_run_started(session: Session, run_id: int) -> AutomationRun | None:
    run = session.get(AutomationRun, run_id)
    if run is None:
        return None
    run.status = "running"
    run.started_at = datetime.datetime.utcnow()
    session.commit()
    session.refresh(run)
    return run


def mark_run_finished(
    session: Session, run_id: int, status: str = "done"
) -> AutomationRun | None:
    run = session.get(AutomationRun, run_id)
    if run is None:
        return None
    run.status = status
    run.finished_at = datetime.datetime.utcnow()
    session.commit()
    session.refresh(run)
    return run


def mark_run_failed(session: Session, run_id: int, error: str) -> AutomationRun | None:
    run = session.get(AutomationRun, run_id)
    if run is None:
        return None
    run.status = "failed"
    run.error = error
    run.finished_at = datetime.datetime.utcnow()
    session.commit()
    session.refresh(run)
    return run


def append_run_warning(session: Session, run_id: int, message: str) -> AutomationRun | None:
    run = session.get(AutomationRun, run_id)
    if run is None:
        return None
    run.error = f"{run.error}\n{message}" if run.error else message
    session.commit()
    session.refresh(run)
    return run


def increment_run_counters(session: Session, run_id: int, **deltas: int) -> AutomationRun | None:
    for field in deltas:
        if field not in _COUNTER_FIELDS:
            raise ValueError(f"Unknown automation run counter: {field}")

    if not deltas:
        return get_automation_run(session, run_id)

    # Atomic column-level increment (col = col + delta) done entirely in SQL,
    # rather than a Python-side read-then-write. This is what makes it safe
    # under concurrent calls from different threads/sessions (as happens here,
    # since the automation pipeline processes results in a thread pool): each
    # UPDATE reads the current on-disk value at write time, so two concurrent
    # increments can no longer clobber each other (the read-modify-write race
    # that silently dropped counts before).
    update_values = {
        getattr(AutomationRun, field): getattr(AutomationRun, field) + delta
        for field, delta in deltas.items()
    }
    session.query(AutomationRun).filter(AutomationRun.id == run_id).update(
        update_values, synchronize_session=False
    )
    session.commit()

    return get_automation_run(session, run_id)