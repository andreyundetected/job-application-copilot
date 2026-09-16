from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse

from ui.common.i18n import SUPPORTED_LANGUAGES

router = APIRouter(prefix="")


@router.post("/set-language")
def set_language(lang: str = Form(...)):
    response = JSONResponse({"status": "ok"})
    if lang in SUPPORTED_LANGUAGES:
        response.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365)
    return response