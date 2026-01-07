import os
import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.error import BadRequest

from config import BOT_TOKEN, ADMIN_IDS, MAX_DOWNLOADS_PER_USER, DEFAULT_DOWNLOAD_PATH
from plugins.scraper import Scraper
from plugins.downloader import Downloader
from plugins.exceptions import RequestBlocked, DriverNotFound
from plugins.helper import is_valid_anime, get_episodes
from database import DatabaseManager

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global variables
user_sessions: Dict[int, Dict] = {}
db_manager = DatabaseManager()

class AnimeDownloaderBot:
    def __init__(self):
        self.app = Application.builder().token(BOT_TOKEN).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup all command handlers"""
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("download", self.download_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("cancel", self.cancel_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        
        # Callback query handler for inline buttons
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
        
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
/stats - View your download statistics

📝 **Usage Examples:**
• Send me an AnimeHeaven URL
• Use: /download <url> 1-10
• Use: /download <url> 5 (for single episode)

⚠️ **Note:** Please be patient as downloading may take some time.
        """
        await update.message.reply_text(welcome_msg)
        
        # Register user in database
        db_manager.add_user(user.id, user.first_name, user.username)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a message when the command /help is issued."""
        help_msg = """
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
• 1-5,8,10 → Downloads episodes 1-5, 8, and 10

⏱️ **Limits:**
• Max {MAX_DOWNLOADS_PER_USER} downloads per user at a time
• Files are automatically deleted after 24 hours

❓ **Need Help?** Contact @admin_username
        """.format(MAX_DOWNLOADS_PER_USER=MAX_DOWNLOADS_PER_USER)
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
        user_downloads = db_manager.get_user_active_downloads(user_id)
        if len(user_downloads) >= MAX_DOWNLOADS_PER_USER:
            await update.message.reply_text(
                f"⚠️ You have reached the maximum concurrent downloads limit ({MAX_DOWNLOADS_PER_USER}).\n"
                "Please wait for your current downloads to complete or cancel them using /cancel."
            )
            return
        
        # Validate URL
        if not is_valid_anime(anime_url):
            await update.message.reply_text("❌ Invalid anime URL format.")
            return
        
        # Parse episode range
        episodes = get_episodes(episode_range)
        if not episodes:
            await update.message.reply_text("❌ Invalid episode range format.\nUse: 1-10 or 5 or 1,2,3")
            return
        
        if len(episodes) > 10:
            await update.message.reply_text("⚠️ Maximum 10 episodes at a time. Please reduce the range.")
            return
        
        # Start download process
        await update.message.reply_text(f"📥 Starting download for {len(episodes)} episode(s)...")
        
        # Create user session
        user_sessions[user_id] = {
            'anime_url': anime_url,
            'episodes': episodes,
            'current_episode': 0,
            'total_episodes': len(episodes),
            'status': 'downloading',
            'message': update.message
        }
        
        # Start download in background
        asyncio.create_task(self.process_download(user_id, anime_url, episodes))
    
    async def process_download(self, user_id: int, anime_url: str, episodes: list):
        """Process anime download in background."""
        try:
            # Initialize scraper and downloader
            scraper = Scraper(anime_url)
            downloader = Downloader(DEFAULT_DOWNLOAD_PATH)
            
            for episode in episodes:
                if user_id not in user_sessions:
                    break
                    
                user_sessions[user_id]['current_episode'] = episode
                
                # Get download links
                videos = None
                retry_count = 0
                
                while videos is None and retry_count < 3:
                    try:
                        videos = scraper.get(str(episode))
                    except RequestBlocked:
                        retry_count += 1
                        await asyncio.sleep(30)
                
                if not videos:
                    logger.error(f"No videos found for episode {episode}")
                    continue
                
                # Download the video
                filename = f"Episode-{episode}.mp4"
                await self.send_status(user_id, f"⬇️ Downloading Episode {episode}...")
                
                try:
                    downloader.download(filename, videos[0])
                    
                    # Record download in database
                    db_manager.add_download(
                        user_id=user_id,
                        anime_url=anime_url,
                        episode=episode,
                        file_path=downloader.get_downloads()[filename]
                    )
                    
                    # Send file to user
                    await self.send_file_to_user(user_id, downloader.get_downloads()[filename], episode)
                    
                except Exception as e:
                    logger.error(f"Download failed for episode {episode}: {e}")
                    await self.send_status(user_id, f"❌ Failed to download Episode {episode}")
            
            # Clean up
            if user_id in user_sessions:
                await self.send_status(user_id, "✅ All downloads completed!")
                del user_sessions[user_id]
                
        except Exception as e:
            logger.error(f"Download process error: {e}")
            if user_id in user_sessions:
                await self.send_status(user_id, f"❌ Error occurred: {str(e)}")
                del user_sessions[user_id]
    
    async def send_file_to_user(self, user_id: int, file_path: str, episode: int):
        """Send downloaded file to user."""
        try:
            with open(file_path, 'rb') as file:
                # Find the user's message to reply to
                if user_id in user_sessions:
                    message = user_sessions[user_id]['message']
                    await message.reply_document(
                        document=file,
                        caption=f"✅ Episode {episode} Downloaded",
                        filename=f"Episode_{episode}.mp4"
                    )
            
            # Delete file after sending
            os.remove(file_path)
            
        except BadRequest as e:
            logger.error(f"Failed to send file: {e}")
            if user_id in user_sessions:
                await self.send_status(user_id, f"❌ File too large for Telegram (max 50MB)")
    
    async def send_status(self, user_id: int, message: str):
        """Send status update to user."""
        if user_id in user_sessions:
            try:
                msg_obj = user_sessions[user_id]['message']
                await msg_obj.reply_text(message)
            except Exception as e:
                logger.error(f"Failed to send status: {e}")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check download status."""
        user_id = update.effective_user.id
        
        if user_id in user_sessions:
            session = user_sessions[user_id]
            status_msg = f"""
📊 **Download Status**

🔗 URL: {session['anime_url'][:50]}...
📺 Episodes: {session['current_episode']}/{session['total_episodes']}
🔄 Status: {session['status'].title()}
            """
            await update.message.reply_text(status_msg)
        else:
            await update.message.reply_text("📭 No active downloads found.")
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel current downloads."""
        user_id = update.effective_user.id
        
        if user_id in user_sessions:
            del user_sessions[user_id]
            await update.message.reply_text("❌ Downloads cancelled.")
        else:
            await update.message.reply_text("📭 No active downloads to cancel.")
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user statistics."""
        user_id = update.effective_user.id
        stats = db_manager.get_user_stats(user_id)
        
        stats_msg = f"""
📈 **Your Statistics**

👤 User: {update.effective_user.first_name}
📥 Total Downloads: {stats['total_downloads']}
📊 Successful: {stats['successful_downloads']}
❌ Failed: {stats['failed_downloads']}
⏰ Last Download: {stats['last_download'] or 'Never'}
        """
        await update.message.reply_text(stats_msg)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle direct messages with anime URLs."""
        text = update.message.text
        
        if is_valid_anime(text):
            # Send options for download
            keyboard = [
                [InlineKeyboardButton("Download All Episodes", callback_data=f"download_all:{text}")],
                [InlineKeyboardButton("Select Episodes", callback_data=f"select_eps:{text}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🎬 Anime URL detected! What would you like to download?",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                "🤔 I only accept AnimeHeaven URLs for now.\n"
                "Please send a valid AnimeHeaven URL or use /help for instructions."
            )
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        if data.startswith("download_all:"):
            anime_url = data.split(":", 1)[1]
            await query.edit_message_text("Please send episode range (e.g., 1-10):")
            # Store anime URL temporarily for next message
            context.user_data['pending_anime_url'] = anime_url
            
        elif data.startswith("select_eps:"):
            anime_url = data.split(":", 1)[1]
            await query.edit_message_text(
                "Please send episode numbers (e.g., 1,3,5 or 1-5):"
            )
            context.user_data['pending_anime_url'] = anime_url
    
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

if __name__ == '__main__':
    bot = AnimeDownloaderBot()
    bot.run()
