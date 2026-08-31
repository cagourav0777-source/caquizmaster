import os
import sys
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
MONGO_URI = os.getenv("MONGO_URI", "").strip()
DEFAULT_QUIZ_INTERVAL_MINUTES = int(os.getenv("DEFAULT_QUIZ_INTERVAL_MINUTES", "30"))
QUIZ_OPEN_PERIOD_SECONDS = int(os.getenv("QUIZ_OPEN_PERIOD_SECONDS", "60"))

super_admins_raw = os.getenv("SUPER_ADMIN_IDS", "").strip()
SUPER_ADMIN_IDS: set[int] = {int(x.strip()) for x in super_admins_raw.split(",") if x.strip().isdigit()}

# Application Constants
MAX_QUESTIONS_PER_TEST = 200
BROADCAST_DELAY_SECONDS = 0.05
QUIZ_CLEANUP_INTERVAL_MINUTES = 15
QUIZ_AUTO_DELETE_HOURS = 24
MOCK_TEST_START_DELAY_SECONDS = 3
INITIAL_QUIZ_DELAY_SECONDS = 10

# 🌙 Daily Midnight Cleanup Settings
DAILY_CLEANUP_ENABLED = True
DAILY_CLEANUP_HOUR = 0  # 0 = Midnight (12:00 AM), 1 = 1 AM, etc.
DAILY_CLEANUP_MINUTE = 0  # 0 minutes past the hour

if not BOT_TOKEN:
    sys.exit("Error: BOT_TOKEN is missing. Please set it in your environment.")

if not MONGO_URI:
    sys.exit("Error: MONGO_URI is missing. Please set it in your environment.")
