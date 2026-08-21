import os
import sys
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
DEFAULT_QUIZ_INTERVAL_MINUTES = int(os.getenv("DEFAULT_QUIZ_INTERVAL_MINUTES", "30"))
QUIZ_OPEN_PERIOD_SECONDS = int(os.getenv("QUIZ_OPEN_PERIOD_SECONDS", "60"))
DB_PATH = os.getenv("DB_PATH", "quiz_bot.db").strip()

super_admins_raw = os.getenv("SUPER_ADMIN_IDS", "").strip()
SUPER_ADMIN_IDS: set[int] = {int(x.strip()) for x in super_admins_raw.split(",") if x.strip().isdigit()}

if not BOT_TOKEN:
    sys.exit("Error: BOT_TOKEN is missing. Please set it in your environment.")
