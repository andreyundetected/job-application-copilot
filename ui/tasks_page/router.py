from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.db.crud import task_statuses as task_statuses_crud
from core.db.session import get_session
from core.tasks.watchdog import pop_error_events

router = APIRouter(prefix="/api/tasks")


@router.get("/stuck-errors")
def stuck_errors():
    return {"events": pop_error_events()}


@router.get("/status")
def task_status(ids: str, session: Session = Depends(get_session)):
    task_ids = [int(item) for item in ids.split(",") if item.strip()]
    tasks = task_statuses_crud.list_task_statuses(session, task_ids)

    return {
        "tasks": [
            {
                "id": task.id,
                "status": task.status,
                "result": task.result,
                "error": task.error,
            }
            for task in tasks
        ]
    }