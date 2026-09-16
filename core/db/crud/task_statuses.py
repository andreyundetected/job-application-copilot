from sqlalchemy.orm import Session

from core.db.models import TaskStatus


def create_task_status(session: Session, task_type: str) -> TaskStatus:
    task = TaskStatus(task_type=task_type, status="pending")
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def get_task_status(session: Session, task_id: int) -> TaskStatus | None:
    return session.get(TaskStatus, task_id)


def list_task_statuses(session: Session, task_ids: list[int]) -> list[TaskStatus]:
    return session.query(TaskStatus).filter(TaskStatus.id.in_(task_ids)).all()


def mark_task_processing(session: Session, task_id: int) -> TaskStatus | None:
    task = session.get(TaskStatus, task_id)
    if task is None:
        return None
    task.status = "processing"
    session.commit()
    session.refresh(task)
    return task


def mark_task_done(session: Session, task_id: int, result: dict) -> TaskStatus | None:
    task = session.get(TaskStatus, task_id)
    if task is None:
        return None
    task.status = "done"
    task.result = result
    session.commit()
    session.refresh(task)
    return task


def mark_task_failed(session: Session, task_id: int, error: str) -> TaskStatus | None:
    task = session.get(TaskStatus, task_id)
    if task is None:
        return None
    task.status = "failed"
    task.error = error
    session.commit()
    session.refresh(task)
    return task