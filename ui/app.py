import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from core.db.crud.tailoring_permissions import seed_default_tailoring_permissions
from core.db.session import SessionLocal, init_db
from core.discovery.scheduler import start_discovery_schedulers, stop_discovery_schedulers
from core.discovery_db.session import init_discovery_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("core").setLevel(logging.INFO)
from ui.automation_page.router import router as automation_router
from ui.dashboard_page.router import router as dashboard_router
from ui.evaluator_page.router import router as evaluator_router
from ui.language_router import router as language_router
from ui.questions_page.router import router as questions_router
from ui.settings_page.router import router as settings_router
from ui.tailoring_page.router import router as tailoring_router
from ui.tasks_page.router import router as tasks_router
from ui.tracker_page.router import router as tracker_router

app = FastAPI(title="Resume Tailoring Pipeline")

app.mount("/static", StaticFiles(directory="ui/common/static"), name="static")

app.include_router(dashboard_router)
app.include_router(evaluator_router)
app.include_router(settings_router)
app.include_router(tasks_router)
app.include_router(tailoring_router)
app.include_router(questions_router)
app.include_router(tracker_router)
app.include_router(automation_router)
app.include_router(language_router)


@app.on_event("startup")
def on_startup():
    init_db()
    init_discovery_db()

    session = SessionLocal()
    try:
        seed_default_tailoring_permissions(session)
    finally:
        session.close()

    start_discovery_schedulers()


@app.on_event("shutdown")
def on_shutdown():
    stop_discovery_schedulers()