import os
import sys
import logging

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Now import other modules
from bot import AnimeDownloaderBot

if __name__ == '__main__':
    # Setup basic logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    
    # Initialize and run bot
    bot = AnimeDownloaderBot()
    bot.run()
