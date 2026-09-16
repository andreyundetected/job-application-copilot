from core.db.crud import task_statuses as task_statuses_crud
from core.db.session import SessionLocal
from core.tasks.executor import submit_task


def run_tracked_task(task_type: str, func, *args, **kwargs) -> int:
    session = SessionLocal()
    try:
        task = task_statuses_crud.create_task_status(session, task_type=task_type)
        task_id = task.id
    finally:
        session.close()

    submit_task(_execute_and_record, task_id, func, *args, **kwargs)
    return task_id


def _execute_and_record(task_id: int, func, *args, **kwargs):
    session = SessionLocal()
    try:
        task_statuses_crud.mark_task_processing(session, task_id)
    finally:
        session.close()

    session = SessionLocal()
    try:
        result = func(*args, **kwargs)
        task_statuses_crud.mark_task_done(session, task_id, result=result)
    except Exception as error:
        task_statuses_crud.mark_task_failed(session, task_id, error=str(error))
    finally:
        session.close()