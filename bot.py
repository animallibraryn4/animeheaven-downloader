import os
import sys
import logging
import asyncio
from typing import Dict, Optional

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters
)

# Add plugins directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'plugins'))

# Import from config (same directory)
from config import BOT_TOKEN, ADMIN_IDS, MAX_DOWNLOADS_PER_USER, DEFAULT_DOWNLOAD_PATH
from plugins.scraper import Scraper
from plugins.downloader import Downloader
from plugins.helper import is_valid_anime, get_episodes

logger = logging.getLogger(__name__)

class AnimeDownloaderBot:
    def __init__(self):
        self.app = Application.builder().token(BOT_TOKEN).build()
        self.user_sessions: Dict[int, Dict] = {}
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup all command handlers"""
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("download", self.download_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("cancel", self.cancel_command))
        
        # Message handler for anime URLs
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Error handler
        self.app.add_error_handler(self.error_handler)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a message when the command /start is issued."""
        user = update.effective_user
        welcome_msg = f"""
👋 Hello {user.first_name}!

Welcome to Anime Downloader Bot! 🤖

I can help you download anime episodes from AnimeHeaven.

📌 **Available Commands:**
/start - Start the bot
/help - Show help message
/download <anime_url> <episode_range> - Download anime episodes
/status - Check download status
/cancel - Cancel current download

📝 **Usage Examples:**
• Send me an AnimeHeaven URL
• Use: /download <url> 1-10
• Use: /download <url> 5 (for single episode)

⚠️ **Note:** Please be patient as downloading may take some time.
        """
        await update.message.reply_text(welcome_msg)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a message when the command /help is issued."""
        help_msg = f"""
📖 **Help Guide**

🔗 **How to get AnimeHeaven URL:**
1. Go to https://animeheaven.eu/
2. Search for your anime
3. Copy the URL from address bar
4. Send it to me

📥 **Download Commands:**
• Send me the AnimeHeaven URL directly
• Or use: /download <url> <episode_range>

🎯 **Episode Range Examples:**
• 1-10 → Downloads episodes 1 through 10
• 5 → Downloads only episode 5

⏱️ **Limits:**
• Max {MAX_DOWNLOADS_PER_USER} downloads per user at a time

❓ **Need Help?** Contact administrator
        """
        await update.message.reply_text(help_msg)
    
    async def download_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /download command with URL and episode range."""
        user_id = update.effective_user.id
        args = context.args
        
        if len(args) < 2:
            await update.message.reply_text(
                "❌ Please provide both URL and episode range.\n"
                "Usage: /download <anime_url> <episode_range>\n"
                "Example: /download https://animeheaven.eu/i.php?a=Naruto 1-10"
            )
            return
        
        anime_url = args[0]
        episode_range = args[1]
        
        # Check if user has reached download limit
        if user_id in self.user_sessions:
            await update.message.reply_text(
                f"⚠️ You already have an active download session.\n"
                "Please wait for it to complete or use /cancel."
            )
            return
        
        # Validate URL
        if not is_valid_anime(anime_url):
            await update.message.reply_text("❌ Invalid anime URL format.")
            return
        
        # Parse episode range
        episodes = get_episodes(episode_range)
        if not episodes:
            await update.message.reply_text("❌ Invalid episode range format.\nUse: 1-10 or 5")
            return
        
        if len(episodes) > 10:
            await update.message.reply_text("⚠️ Maximum 10 episodes at a time. Please reduce the range.")
            return
        
        # Start download process
        await update.message.reply_text(f"📥 Starting download for {len(episodes)} episode(s)...")
        
        # Create user session
        self.user_sessions[user_id] = {
            'anime_url': anime_url,
            'episodes': episodes,
            'current_episode': 0,
            'total_episodes': len(episodes),
            'status': 'downloading'
        }
        
        # Start download in background
        asyncio.create_task(self.process_download(user_id, anime_url, episodes, update.message))
    
    async def process_download(self, user_id: int, anime_url: str, episodes: list, message):
        """Process anime download in background."""
        try:
            # Initialize scraper and downloader
            scraper = Scraper(anime_url)
            downloader = Downloader(DEFAULT_DOWNLOAD_PATH)
            
            for episode in episodes:
                if user_id not in self.user_sessions:
                    break
                    
                self.user_sessions[user_id]['current_episode'] = episode
                
                # Get download links
                videos = None
                retry_count = 0
                
                while videos is None and retry_count < 3:
                    try:
                        videos = scraper.get(str(episode))
                        if videos:
                            await message.reply_text(f"🔍 Found download link for Episode {episode}")
                        else:
                            await message.reply_text(f"❌ No video found for Episode {episode}")
                            continue
                    except Exception as e:
                        retry_count += 1
                        logger.error(f"Error getting episode {episode}: {e}")
                        await asyncio.sleep(5)
                
                if not videos:
                    logger.error(f"No videos found for episode {episode}")
                    continue
                
                # Download the video
                filename = f"Episode_{episode}.mp4"
                await message.reply_text(f"⬇️ Downloading Episode {episode}...")
                
                try:
                    success = downloader.download(filename, videos[0])
                    
                    if success:
                        # Get file path
                        downloads = downloader.get_downloads()
                        if filename in downloads:
                            file_path = downloads[filename]
                            
                            # Send file to user
                            await self.send_file_to_user(message, file_path, episode)
                        else:
                            await message.reply_text(f"❌ Failed to save Episode {episode}")
                    else:
                        await message.reply_text(f"❌ Download failed for Episode {episode}")
                    
                except Exception as e:
                    logger.error(f"Download failed for episode {episode}: {e}")
                    await message.reply_text(f"❌ Error downloading Episode {episode}: {str(e)[:100]}")
            
            # Clean up
            if user_id in self.user_sessions:
                await message.reply_text("✅ All downloads completed!")
                del self.user_sessions[user_id]
                
            # Clean up downloader files
            downloader.cleanup()
            # Close scraper
            if hasattr(scraper, 'close'):
                scraper.close()
                
        except Exception as e:
            logger.error(f"Download process error: {e}")
            if user_id in self.user_sessions:
                await message.reply_text(f"❌ Error occurred: {str(e)[:200]}")
                del self.user_sessions[user_id]
    
    async def send_file_to_user(self, message, file_path: str, episode: int):
        """Send downloaded file to user."""
        try:
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                
                if file_size > 50 * 1024 * 1024:  # 50MB limit
                    await message.reply_text(f"⚠️ Episode {episode} is too large ({file_size/1024/1024:.1f}MB). Max 50MB for Telegram.")
                    os.remove(file_path)
                    return
                
                with open(file_path, 'rb') as file:
                    await message.reply_document(
                        document=file,
                        caption=f"✅ Episode {episode} Downloaded",
                        filename=f"Episode_{episode}.mp4"
                    )
                
                # Delete file after sending
                os.remove(file_path)
            else:
                await message.reply_text(f"❌ File not found for Episode {episode}")
                
        except Exception as e:
            logger.error(f"Failed to send file: {e}")
            await message.reply_text(f"❌ Failed to send Episode {episode}: {str(e)[:100]}")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check download status."""
        user_id = update.effective_user.id
        
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            status_msg = f"""
📊 **Download Status**

🔗 Anime: {session['anime_url'][:50]}...
📺 Progress: {session['current_episode']}/{session['total_episodes']}
🔄 Status: {session['status'].title()}
            """
            await update.message.reply_text(status_msg)
        else:
            await update.message.reply_text("📭 No active downloads found.")
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel current downloads."""
        user_id = update.effective_user.id
        
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
            await update.message.reply_text("❌ Downloads cancelled.")
        else:
            await update.message.reply_text("📭 No active downloads to cancel.")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle direct messages with anime URLs."""
        text = update.message.text
        
        if is_valid_anime(text):
            await update.message.reply_text(
                f"🎬 Anime URL detected!\n\n"
                f"To download episodes, use:\n"
                f"`/download {text} 1-10`\n\n"
                f"Replace `1-10` with your desired episode range.",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                "🤔 I only accept AnimeHeaven URLs for now.\n"
                "Please send a valid AnimeHeaven URL or use /help for instructions.\n\n"
                "Example: `http://animeheaven.eu/i.php?a=Naruto`",
                parse_mode='Markdown'
            )
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors."""
        logger.error(f"Exception while handling an update: {context.error}")
        
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "❌ An error occurred. Please try again later."
                )
        except Exception:
            pass
    
    def run(self):
        """Start the bot."""
        logger.info("Starting Anime Downloader Bot...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)
