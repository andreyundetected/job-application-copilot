import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "freellmapi")

FREELLMAPI_KEY = os.getenv("FREELLMAPI_KEY", "")
FREELLMAPI_BASE_URL = os.getenv("FREELLMAPI_BASE_URL", "http://localhost:3001/v1")
FREELLMAPI_MODEL = os.getenv("FREELLMAPI_MODEL", "auto")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'app.db'}")

OUTPUT_DIR = BASE_DIR / "output"
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"

OUTPUT_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)

TASK_MAX_WORKERS = int(os.getenv("TASK_MAX_WORKERS", "25"))

SERPENT_API_KEY = os.getenv("SERPENT_API_KEY", "")
SERPENT_BASE_URL = os.getenv("SERPENT_BASE_URL", "https://apiserpent.com/api/search/quick")

SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
SERPER_BASE_URL = os.getenv("SERPER_BASE_URL", "https://google.serper.dev/search")

# Order to try configured search providers in; a provider is skipped entirely if its
# API key is empty. On failure, the next provider in the list is tried automatically.
SEARCH_PROVIDER_ORDER = os.getenv("SEARCH_PROVIDER_ORDER", "serper,serpent")

AUTOMATION_MAX_WORKERS = int(os.getenv("AUTOMATION_MAX_WORKERS", "10"))