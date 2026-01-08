#!/usr/bin/env python3
import os
import sys
import logging
import asyncio
import tempfile
from typing import Dict, List, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# Add working scraper
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from working_scraper import AnimeHeavenDownloader
except ImportError:
    # Create minimal version
    class AnimeHeavenDownloader:
        def search_anime(self, query):
            return []
        def get_video_url(self, anime_code, episode):
            return None
        def download_video(self, url, filename):
            return None

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class CompleteAnimeBot:
    def __init__(self, token):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.downloader = AnimeHeavenDownloader()
        self.user_sessions = {}  # Store user download sessions
        
        self.setup_handlers()
    
    def setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("search", self.search_command))
        self.app.add_handler(CommandHandler("download", self.download_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("cancel", self.cancel_command))
        self.app.add_handler(CallbackQueryHandler(self.button_handler))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        await update.message.reply_text(
            f"🎬 *Anime Downloader Bot*\n\n"
            f"Hello {user.first_name}! I can help you download anime episodes.\n\n"
            "*Features:*\n"
            "• Search anime by name\n"
            "• Download specific episodes\n"
            "• Direct video downloads\n\n"
            "*How to use:*\n"
            "1. Type an anime name (e.g., `Naruto`)\n"
            "2. Select the anime from results\n"
            "3. Enter episode number (e.g., `1` or `1-5`)\n"
            "4. I'll download and send you the video\n\n"
            "*Commands:*\n"
            "/search - Search for anime\n"
            "/download - Direct download\n"
            "/help - Show help guide\n"
            "/status - Check download status\n"
            "/cancel - Cancel download",
            parse_mode='Markdown'
        )
    
    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            text = update.message.text
            if text and not text.startswith('/'):
                query = text
            else:
                await update.message.reply_text(
                    "Please type an anime name to search:\n"
                    "`/search Naruto` or just type `Naruto`",
                    parse_mode='Markdown'
                )
                return
        else:
            query = ' '.join(context.args)
        
        await update.message.reply_text(f"🔍 Searching for '{query}'...")
        
        # Search anime
        results = self.downloader.search_anime(query)
        
        if not results:
            await update.message.reply_text(
                f"❌ No results found for '{query}'.\n\n"
                "*Try these popular anime:*\n"
                "• Naruto / Naruto Shippuden\n"
                "• One Piece\n"
                "• Demon Slayer\n"
                "• Attack on Titan\n"
                "• Jujutsu Kaisen\n"
                "• My Hero Academia",
                parse_mode='Markdown'
            )
            return
        
        # Create inline keyboard
        keyboard = []
        for result in results:
            # Show episode count if available
            title = result['title']
            if result.get('episodes', 0) > 0:
                title += f" ({result['episodes']} eps)"
            
            callback_data = f"select:{result['id']}:{result.get('title', '')}"
            keyboard.append([InlineKeyboardButton(title, callback_data=callback_data)])
        
        # Add search link button
        if len(results) == 1 and results[0]['id'] == 'search':
            keyboard.append([InlineKeyboardButton("🔗 Open Search Results", url=results[0]['search_url'])])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"📋 Found {len(results)} result(s) for '{query}':\n"
            "Click on an anime to download episodes.",
            reply_markup=reply_markup
        )
    
    async def download_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Direct download command: /download <anime> <episode>"""
        if len(context.args) < 2:
            await update.message.reply_text(
                "Usage: `/download <anime> <episode>`\n\n"
                "*Examples:*\n"
                "`/download naruto 1` - Download episode 1\n"
                "`/download naruto 1-5` - Download episodes 1 to 5\n\n"
                "*Available anime:*\n"
                "• naruto / naruto-shippuden\n"
                "• one-piece\n"
                "• demon-slayer\n"
                "• attack-on-titan",
                parse_mode='Markdown'
            )
            return
        
        anime_name = context.args[0].lower()
        episode_range = context.args[1]
        
        # Parse episode range
        episodes = self.parse_episode_range(episode_range)
        if not episodes:
            await update.message.reply_text(
                "Invalid episode format. Use:\n"
                "• `1` for single episode\n"
                "• `1-5` for range\n"
                "• `1,3,5` for specific episodes"
            )
            return
        
        # Limit to 3 episodes max
        if len(episodes) > 3:
            await update.message.reply_text("⚠️ Maximum 3 episodes at a time. Downloading first 3 episodes.")
            episodes = episodes[:3]
        
        user_id = update.effective_user.id
        
        # Check if user already has active download
        if user_id in self.user_sessions:
            await update.message.reply_text("⚠️ You already have an active download. Wait for it to complete.")
            return
        
        await update.message.reply_text(f"📥 Starting download of {len(episodes)} episode(s)...")
        
        # Start download in background
        asyncio.create_task(
            self.download_episodes(user_id, anime_name, episodes, update.message)
        )
    
    async def download_episodes(self, user_id: int, anime_code: str, episodes: List[int], message):
        """Download multiple episodes"""
        self.user_sessions[user_id] = {
            'status': 'downloading',
            'total': len(episodes),
            'completed': 0,
            'failed': []
        }
        
        try:
            for episode in episodes:
                # Update status
                self.user_sessions[user_id]['current'] = episode
                
                await message.reply_text(f"⬇️ Downloading Episode {episode}...")
                
                # Get video URL
                video_url = self.downloader.get_video_url(anime_code, episode)
                
                if not video_url:
                    await message.reply_text(f"❌ Could not find video for Episode {episode}")
                    self.user_sessions[user_id]['failed'].append(episode)
                    continue
                
                # Create temp file
                with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp_file:
                    filename = tmp_file.name
                
                # Download video
                downloaded_file = self.downloader.download_video(video_url, filename)
                
                if downloaded_file and os.path.exists(downloaded_file):
                    # Check file size (Telegram limit: 50MB for bots)
                    file_size = os.path.getsize(downloaded_file)
                    
                    if file_size > 50 * 1024 * 1024:  # 50MB limit
                        await message.reply_text(
                            f"⚠️ Episode {episode} is too large ({file_size/1024/1024:.1f}MB). "
                            "Telegram limit is 50MB.\n"
                            f"Direct URL: {video_url[:100]}..."
                        )
                        os.remove(downloaded_file)
                    else:
                        # Send video to user
                        try:
                            with open(downloaded_file, 'rb') as video_file:
                                await message.reply_video(
                                    video=video_file,
                                    caption=f"✅ Episode {episode}",
                                    supports_streaming=True
                                )
                            self.user_sessions[user_id]['completed'] += 1
                        except Exception as e:
                            await message.reply_text(f"❌ Failed to send Episode {episode}: {str(e)[:100]}")
                            self.user_sessions[user_id]['failed'].append(episode)
                        
                        # Clean up
                        os.remove(downloaded_file)
                else:
                    await message.reply_text(f"❌ Download failed for Episode {episode}")
                    self.user_sessions[user_id]['failed'].append(episode)
            
            # Send summary
            completed = self.user_sessions[user_id]['completed']
            failed = len(self.user_sessions[user_id]['failed'])
            
            summary = f"✅ Download Complete!\n\n"
            summary += f"Successfully downloaded: {completed} episode(s)\n"
            summary += f"Failed: {failed} episode(s)\n"
            
            if failed > 0:
                summary += f"\nFailed episodes: {', '.join(map(str, self.user_sessions[user_id]['failed']))}"
                summary += "\n\n*Possible reasons:*\n"
                summary += "• Episode not available\n"
                summary += "• Website blocked in your region (use VPN)\n"
                summary += "• File too large for Telegram\n"
            
            await message.reply_text(summary, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Download error: {e}")
            await message.reply_text(f"❌ Download error: {str(e)[:200]}")
        
        finally:
            # Clean up session
            if user_id in self.user_sessions:
                del self.user_sessions[user_id]
    
    def parse_episode_range(self, text: str) -> List[int]:
        """Parse episode range"""
        try:
            episodes = []
            text = text.replace(' ', '')
            
            if '-' in text:
                # Range like 1-5
                start, end = map(int, text.split('-'))
                episodes = list(range(start, end + 1))
            elif ',' in text:
                # List like 1,3,5
                episodes = [int(x) for x in text.split(',')]
            else:
                # Single episode
                episodes = [int(text)]
            
            # Limit and validate
            episodes = [ep for ep in episodes if 1 <= ep <= 1000]
            return sorted(set(episodes))[:10]  # Max 10 episodes
            
        except:
            return []
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data.startswith("select:"):
            parts = data.split(":")
            if len(parts) >= 3:
                anime_code = parts[1]
                anime_name = parts[2]
                
                # Store in context
                context.user_data['selected_anime'] = {
                    'code': anime_code,
                    'name': anime_name
                }
                
                await query.edit_message_text(
                    f"Selected: *{anime_name}*\n\n"
                    "Now send me the episode number(s):\n\n"
                    "*Examples:*\n"
                    "• `1` - Episode 1\n"
                    "• `1-5` - Episodes 1 to 5\n"
                    "• `1,3,5` - Episodes 1, 3, and 5\n\n"
                    "*Note:* Maximum 3 episodes at a time.",
                    parse_mode='Markdown'
                )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle episode number input"""
        text = update.message.text.strip()
        
        # Check if user has selected an anime
        if 'selected_anime' in context.user_data:
            anime_info = context.user_data['selected_anime']
            anime_code = anime_info['code']
            anime_name = anime_info['name']
            
            # Parse episode range
            episodes = self.parse_episode_range(text)
            
            if not episodes:
                await update.message.reply_text(
                    "Invalid episode format. Please send:\n"
                    "• Single number (e.g., `1`)\n"
                    "• Range (e.g., `1-5`)\n"
                    "• List (e.g., `1,3,5`)"
                )
                return
            
            # Limit to 3 episodes
            if len(episodes) > 3:
                await update.message.reply_text("⚠️ Maximum 3 episodes at a time. Downloading first 3 episodes.")
                episodes = episodes[:3]
            
            # Clear selection
            del context.user_data['selected_anime']
            
            user_id = update.effective_user.id
            
            # Check active downloads
            if user_id in self.user_sessions:
                await update.message.reply_text("⚠️ You already have an active download. Wait for it to complete.")
                return
            
            await update.message.reply_text(f"📥 Starting download of {len(episodes)} episode(s) of {anime_name}...")
            
            # Start download
            asyncio.create_task(
                self.download_episodes(user_id, anime_code, episodes, update.message)
            )
            
        else:
            # Treat as search query
            context.args = [text]
            await self.search_command(update, context)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            status_msg = (
                f"📊 *Download Status*\n\n"
                f"Current: Episode {session.get('current', 'N/A')}\n"
                f"Total: {session['total']} episode(s)\n"
                f"Completed: {session['completed']}\n"
                f"Failed: {len(session.get('failed', []))}\n"
                f"Status: {session['status'].title()}"
            )
            await update.message.reply_text(status_msg, parse_mode='Markdown')
        else:
            await update.message.reply_text("📭 No active downloads.")
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
            await update.message.reply_text("❌ Download cancelled.")
        else:
            await update.message.reply_text("📭 No active download to cancel.")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            "📚 *Anime Downloader Bot - Help*\n\n"
            "*How to Download:*\n"
            "1. Search for anime by name\n"
            "2. Select from results\n"
            "3. Enter episode number(s)\n"
            "4. Wait for download\n\n"
            "*Commands:*\n"
            "• /start - Welcome message\n"
            "• /search <name> - Search anime\n"
            "• /download <anime> <episode> - Direct download\n"
            "• /status - Check download progress\n"
            "• /cancel - Cancel download\n"
            "• /help - This message\n\n"
            "*Episode Formats:*\n"
            "• `1` - Single episode\n"
            "• `1-5` - Range\n"
            "• `1,3,5` - Specific episodes\n\n"
            "*Limitations:*\n"
            "• Max 3 episodes at once\n"
            "• Max 50MB per file (Telegram limit)\n"
            "• May require VPN for some regions\n\n"
            "*Popular Anime Codes:*\n"
            "• naruto / naruto-shippuden\n"
            "• one-piece\n"
            "• demon-slayer\n"
            "• attack-on-titan\n"
            "• jujutsu-kaisen\n"
            "• my-hero-academia"
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    def run(self):
        logger.info("Starting Complete Anime Bot...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)

# Install required packages
def install_requirements():
    import subprocess
    import sys
    
    requirements = [
        'python-telegram-bot==20.7',
        'requests',
        'cloudscraper'
    ]
    
    for package in requirements:
        try:
            __import__(package.replace('==', '.').split('.')[0])
        except ImportError:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

if __name__ == '__main__':
    # Install requirements
    install_requirements()
    
    # Get bot token
    token = os.getenv('BOT_TOKEN')
    if not token:
        # Try to read from .env file
        try:
            with open('.env', 'r') as f:
                for line in f:
                    if line.startswith('BOT_TOKEN='):
                        token = line.strip().split('=', 1)[1]
                        break
        except:
            pass
        
        if not token:
            print("="*60)
            print("BOT TOKEN REQUIRED")
            print("="*60)
            print("Please create a .env file with:")
            print("BOT_TOKEN=your_bot_token_here")
            print("\nOr set environment variable:")
            print("export BOT_TOKEN='your_bot_token_here'")
            print("\nOr enter your token below:")
            token = input("Bot Token: ").strip()
    
    if not token or len(token) < 10:
        print("❌ Invalid bot token")
        sys.exit(1)
    
    # Create .env file if it doesn't exist
    if not os.path.exists('.env'):
        with open('.env', 'w') as f:
            f.write(f"BOT_TOKEN={token}\n")
    
    print("✅ Starting bot...")
    bot = CompleteAnimeBot(token)
    bot.run()
