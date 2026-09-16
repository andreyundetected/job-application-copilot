from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from core.db.session import init_db
from ui.evaluator_page.router import router as evaluator_router
from ui.settings_page.router import router as settings_router

app = FastAPI(title="Resume Tailoring Pipeline")

app.mount("/static", StaticFiles(directory="ui/common/static"), name="static")

app.include_router(evaluator_router)
app.include_router(settings_router)


@app.on_event("startup")
def on_startup():
    init_db()