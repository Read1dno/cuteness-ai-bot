import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = Path('images')
IMAGES_DIR.mkdir(exist_ok=True)

CUTE_COMMANDS = ['cute', 'сгеу', 'мило', 'куте']

ADMIN_USERNAME = "admin"
BOT_TOKEN = os.getenv('BOT_TOKEN') 
DATABASE_URL = os.getenv('DATABASE_URL') 
ADMIN_ID = int(os.getenv('ADMIN_ID'))
ADMIN_PASSWORD = os.environ.get('ADMIN_PANEL_PASSWORD')
STORAGE_CHAT_ID = int(os.getenv('STORAGE_CHAT_ID'))

NSFW_FILTER_ENABLED = False #WARNING!!!!

MODEL_PATH = 'model/CuteLarge.pt'
DB_PATH = 'cute_bot.db'
RATE_LIMIT_SECONDS = 10
TOP_THRESHOLD = 50
RAW_MIN, RAW_MAX = 0, 100