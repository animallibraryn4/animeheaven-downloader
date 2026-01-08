import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN', '7765824536:')
ADMIN_IDS = list(map(int, os.getenv('ADMIN_IDS', '5380609667').split(','))) if os.getenv('ADMIN_IDS') else []
MAX_DOWNLOADS_PER_USER = int(os.getenv('MAX_DOWNLOADS_PER_USER', '3'))

# Anime Downloader Configuration
ANIMEHEAVEN_ABUSE_MSG = 'You have triggered abuse protection'
BLOCKED_TIMEOUT = int(os.getenv('BLOCKED_TIMEOUT', '120'))
DEFAULT_DOWNLOAD_PATH = 'downloads'
LOG_PATH = 'logs'

# Time Configuration
now = datetime.now().strftime('%d%m%y_%H%M')

# Supported Anime Sources
ANIME_SOURCES = {
    'gogoanime': {
        'base_url': 'https://animeheaven.me',
        'search_url': 'https://animeheaven.me/search.html',
        'episode_pattern': 'https://animeheaven.me/{anime_id}-episode-{episode}'
    },
    'animepahe': {
        'base_url': 'https://animepahe.com',
        'api_url': 'https://animepahe.com/api'
    },
    'zoro': {
        'base_url': 'https://zoro.to',
        'search_url': 'https://zoro.to/search'
    }
}

# Default source
DEFAULT_SOURCE = 'gogoanime'

# Time Configuration
now = datetime.now().strftime('%d%m%y_%H%M')
