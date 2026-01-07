import os
from datetime import datetime

# Bot Configuration
BOT_CONFIG = {
    'MAX_FILE_SIZE': 50 * 1024 * 1024,  # 50MB (Telegram limit)
    'MAX_EPISODES_PER_REQUEST': 5,
    'DOWNLOAD_TIMEOUT': 300,  # 5 minutes
    'REQUEST_DELAY': 2,  # seconds between requests
}

# Anime Sources Configuration
ANIME_SOURCES = {
    'gogoanime': {
        'base_url': 'https://gogoanime3.co',
        'search_url': '/search.html',
        'ajax_url': '/load-list-episode',
    },
    '9anime': {
        'base_url': 'https://9anime.pl',
        'search_url': '/filter',
        'ajax_url': '/ajax/episode/list/',
    }
}

# Download Settings
DOWNLOAD_SETTINGS = {
    'DEFAULT_FORMAT': 'mp4',
    'QUALITY_PREFERENCE': ['1080p', '720p', '480p', '360p'],
    'DEFAULT_DOWNLOAD_PATH': 'downloads',
    'TEMP_PATH': 'temp',
}

# Create necessary directories
def init_directories():
    """Create necessary directories for the bot."""
    directories = [
        DOWNLOAD_SETTINGS['DEFAULT_DOWNLOAD_PATH'],
        DOWNLOAD_SETTINGS['TEMP_PATH'],
        'logs',
        'database'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

# Initialize directories on import
init_directories()

# Get current timestamp for downloads
def get_timestamp():
    return datetime.now().strftime('%Y%m%d_%H%M%S')
