"""Central configuration. Every other module imports from here."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.modify",
]
CREDENTIALS_FILE = BASE_DIR / "credentials" / "credentials.json"
TOKEN_FILE = BASE_DIR / "credentials" / "token.json"


RESUME_DIR = (BASE_DIR / os.getenv("RESUME_DIR", "resumes")).resolve()
DOWNLOAD_DIR = (BASE_DIR / os.getenv("DOWNLOAD_DIR", "downloads")).resolve()
DEFAULT_RESUME = os.getenv("DEFAULT_RESUME", "my_resume.pdf")
DB_PATH = BASE_DIR / "storage" / "agent.db"


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL = os.getenv("MODEL", "gemini-2-flash")
MAX_AGENT_STEPS = int(os.getenv("MAX_AGENT_STEPS", "10"))


MAX_BODY_CHARS = int(os.getenv("MAX_BODY_CHARS", "6000"))
MAX_RESULTS_CAP = 50
MAX_ATTACHMENT_MB = 20


USER_NAME = os.getenv("USER_NAME", "the user")
USER_SIGNATURE = os.getenv("USER_SIGNATURE", USER_NAME)
USER_PROFILE = os.getenv("USER_PROFILE", "")
