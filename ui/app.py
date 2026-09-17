from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from core.db.session import init_db
from ui.dashboard_page.router import router as dashboard_router
from ui.evaluator_page.router import router as evaluator_router
from ui.language_router import router as language_router
from ui.questions_page.router import router as questions_router
from ui.settings_page.router import router as settings_router
from ui.tailoring_page.router import router as tailoring_router
from ui.tasks_page.router import router as tasks_router

app = FastAPI(title="Resume Tailoring Pipeline")

app.mount("/static", StaticFiles(directory="ui/common/static"), name="static")

app.include_router(dashboard_router)
app.include_router(evaluator_router)
app.include_router(settings_router)
app.include_router(tasks_router)
app.include_router(tailoring_router)
app.include_router(questions_router)
app.include_router(language_router)


@app.on_event("startup")
def on_startup():
    init_db()