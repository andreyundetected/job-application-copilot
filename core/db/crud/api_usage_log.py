from sqlalchemy.orm import Session

from core.db.models import ApiUsageLog


def create_usage_log(
    session: Session,
    provider: str,
    operation: str,
    automation_run_id: int | None = None,
    search_result_id: int | None = None,
    job_posting_id: int | None = None,
    requested_num: int | None = None,
    returned_count: int | None = None,
    model: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    reasoning_tokens: int | None = None,
    total_tokens: int | None = None,
    estimated_cost: float | None = None,
    raw_usage: dict | None = None,
) -> ApiUsageLog:
    log = ApiUsageLog(
        provider=provider,
        operation=operation,
        automation_run_id=automation_run_id,
        search_result_id=search_result_id,
        job_posting_id=job_posting_id,
        requested_num=requested_num,
        returned_count=returned_count,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        reasoning_tokens=reasoning_tokens,
        total_tokens=total_tokens,
        estimated_cost=estimated_cost,
        raw_usage=raw_usage,
    )
    session.add(log)
    session.commit()
    session.refresh(log)
    return log


def list_usage_logs_for_run(session: Session, automation_run_id: int) -> list[ApiUsageLog]:
    return (
        session.query(ApiUsageLog)
        .filter(ApiUsageLog.automation_run_id == automation_run_id)
        .order_by(ApiUsageLog.created_at.asc())
        .all()
    )


def sum_usage_for_run(session: Session, automation_run_id: int) -> dict:
    logs = list_usage_logs_for_run(session, automation_run_id)

    totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
        "total_tokens": 0,
        "estimated_cost": 0.0,
        "requested_num": 0,
        "returned_count": 0,
        "by_provider": {},
    }

    for log in logs:
        totals["input_tokens"] += log.input_tokens or 0
        totals["output_tokens"] += log.output_tokens or 0
        totals["reasoning_tokens"] += log.reasoning_tokens or 0
        totals["total_tokens"] += log.total_tokens or 0
        totals["estimated_cost"] += log.estimated_cost or 0.0
        totals["requested_num"] += log.requested_num or 0
        totals["returned_count"] += log.returned_count or 0
        totals["by_provider"][log.provider] = totals["by_provider"].get(log.provider, 0) + 1

    return totals