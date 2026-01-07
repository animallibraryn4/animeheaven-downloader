import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN', '')
ADMIN_IDS = list(map(int, os.getenv('ADMIN_IDS', '5380609667').split(','))) if os.getenv('ADMIN_IDS') else []
MAX_DOWNLOADS_PER_USER = int(os.getenv('MAX_DOWNLOADS_PER_USER', '3'))
MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', '524288000'))  # 500MB in bytes

# Anime Downloader Configuration
ANIMEHEAVEN_ABUSE_MSG = 'You have triggered abuse protection'
BLOCKED_TIMEOUT = int(os.getenv('BLOCKED_TIMEOUT', '120'))
DEFAULT_DOWNLOAD_PATH = 'downloads'
LOG_PATH = 'logs'

# Server Configuration
PORT = int(os.getenv('PORT', '8080'))
HOST = os.getenv('HOST', '0.0.0.0')

# Database Configuration (Optional)
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///anime_bot.db')

# Time Configuration
now = datetime.now().strftime('%d%m%y_%H%M')
