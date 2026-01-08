#!/usr/bin/env python3
import os
import sys
import logging
import asyncio
from typing import Dict, List, Optional
import tempfile

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import working scraper and downloader
try:
    from working_scraper import AnimeHeavenDownloader
    from downloader import SmartDownloader
    from helper import get_episodes
except ImportError:
    # Fallback if imports fail
    class AnimeHeavenDownloader:
        def search_anime(self, query):
            return []
        
        def get_video_url(self, anime_code, episode):
            return None
        
        def download_video(self, url, filename):
            return None
    
    def get_episodes(ep):
        return []

class AlternativeAnimeBot:
    def __init__(self, token):
        self.token = token
        self.app = Application.builder().token(token).build()
        self.scraper = AnimeHeavenDownloader()
        self.user_sessions: Dict[int, Dict] = {}
        self.setup_handlers()
    
    def setup_handlers(self):
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("search", self.search_command))
        self.app.add_handler(CommandHandler("download", self.download_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("cancel", self.cancel_command))
        self.app.add_handler(CallbackQueryHandler(self.button_handler))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🎬 *Alternative Anime Bot*\n\n"
            "I can help you find and download anime episodes.\n\n"
            "*Features:*\n"
            "1. Search for anime\n"
            "2. Get direct download links\n"
            "3. Download episodes to Telegram\n\n"
            "Use /search to find anime or just type the anime name.\n"
            "Use /help for more information.",
            parse_mode='Markdown'
        )
    
    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not context.args:
            text = update.message.text
            if text and not text.startswith('/'):
                query = text
            else:
                await update.message.reply_text("Please type an anime name to search, or use `/search <name>`", parse_mode='Markdown')
                return
        else:
            query = ' '.join(context.args)
        
        await update.message.reply_text(f"🔍 Searching for '{query}'...")
        
        # Search using the working scraper
        results = self.scraper.search_anime(query)
        
        if results:
            # Create buttons for each result
            keyboard = []
            for result in results[:6]:  # Limit to 6 results
                # Store anime info in callback data
                callback_data = f"select:{result['id']}:{result.get('title', 'Unknown')}"
                btn = InlineKeyboardButton(
                    result['title'][:50],
                    callback_data=callback_data
                )
                keyboard.append([btn])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"📋 Found {len(results)} results for '{query}':\n\n"
                "*Click on an anime to select it for download.*\n"
                "After selection, send me the episode number or range.",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"❌ No results found for '{query}'.\n\n"
                "*Try these alternatives:*\n"
                "1. Use more specific search terms\n"
                "2. Try English anime name\n"
                "3. Check spelling",
                parse_mode='Markdown'
            )
    
    async def download_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Direct download command"""
        if len(context.args) < 2:
            await update.message.reply_text(
                """Usage: `/download <anime_name> <episode>`\n"
                "Example: `/download naruto 1`\n"
                "Example: `/download "demon slayer" 1-5`""",
                parse_mode='Markdown'
            )
            return
        
        # Get anime name and episode range
        anime_name = context.args[0]
        episode_range = ' '.join(context.args[1:])
        
        await update.message.reply_text(f"🔍 Searching for '{anime_name}'...")
        
        # Search for anime
        results = self.scraper.search_anime(anime_name)
        
        if not results:
            await update.message.reply_text(f"❌ No anime found with name '{anime_name}'")
            return
        
        # Use first result
        anime = results[0]
        anime_code = anime['id']
        
        # Parse episode range
        episodes = get_episodes(episode_range)
        if not episodes:
            await update.message.reply_text("Invalid episode format. Use: 1, 1-5, or 1,3,5")
            return
        
        # Limit to 5 episodes at once
        episodes = episodes[:5]
        
        user_id = update.effective_user.id
        
        # Check if user already has active download
        if user_id in self.user_sessions:
            await update.message.reply_text("⚠️ You already have an active download. Use /cancel to cancel.")
            return
        
        # Start download
        await update.message.reply_text(f"📥 Downloading {len(episodes)} episode(s) of {anime['title']}...")
        
        asyncio.create_task(
            self.download_episodes(user_id, anime_code, anime['title'], episodes, update.message)
        )
    
    async def download_episodes(self, user_id: int, anime_code: str, anime_title: str, episodes: List[int], message):
        """Download multiple episodes"""
        try:
            self.user_sessions[user_id] = {
                'status': 'downloading',
                'anime': anime_title,
                'current': 0,
                'total': len(episodes),
                'failed': []
            }
            
            downloader = SmartDownloader()
            
            for ep_num in episodes:
                self.user_sessions[user_id]['current'] = ep_num
                
                try:
                    await message.reply_text(f"🔄 Getting video URL for Episode {ep_num}...")
                    
                    # Get video URL
                    video_url = self.scraper.get_video_url(anime_code, ep_num)
                    
                    if not video_url:
                        await message.reply_text(f"❌ No video found for Episode {ep_num}")
                        self.user_sessions[user_id]['failed'].append(ep_num)
                        continue
                    
                    # Download the video
                    filename = f"{anime_title} - Episode {ep_num}.mp4"
                    await message.reply_text(f"⬇️ Downloading Episode {ep_num}...")
                    
                    filepath = self.scraper.download_video(video_url, filename)
                    
                    if filepath and os.path.exists(filepath):
                        # Send to user
                        await self.send_file_to_user(message, filepath, anime_title, ep_num)
                        
                        # Clean up
                        try:
                            os.remove(filepath)
                        except:
                            pass
                    else:
                        await message.reply_text(f"❌ Failed to download Episode {ep_num}")
                        self.user_sessions[user_id]['failed'].append(ep_num)
                    
                except Exception as e:
                    logger.error(f"Error downloading episode {ep_num}: {e}")
                    await message.reply_text(f"❌ Error downloading Episode {ep_num}: {str(e)[:100]}")
                    self.user_sessions[user_id]['failed'].append(ep_num)
            
            # Cleanup
            downloader.cleanup()
            
            # Send summary
            failed_count = len(self.user_sessions[user_id]['failed'])
            success_count = len(episodes) - failed_count
            
            summary = f"""
✅ Download Complete!

Anime: {anime_title}
Successfully downloaded: {success_count} episode(s)
Failed: {failed_count} episode(s)
            """
            
            if self.user_sessions[user_id]['failed']:
                summary += f"\nFailed episodes: {', '.join(map(str, self.user_sessions[user_id]['failed']))}"
            
            await message.reply_text(summary)
            
            # Clear session
            del self.user_sessions[user_id]
            
        except Exception as e:
            logger.error(f"Download process error: {e}")
            if user_id in self.user_sessions:
                await message.reply_text(f"❌ Error: {str(e)[:200]}")
                del self.user_sessions[user_id]
    
    async def send_file_to_user(self, message, filepath: str, anime_title: str, episode: int):
        """Send downloaded file to user"""
        try:
            if os.path.exists(filepath):
                file_size = os.path.getsize(filepath)
                
                # Telegram file size limit
                if file_size > 50 * 1024 * 1024:
                    await message.reply_text(
                        f"⚠️ Episode {episode} is too large ({file_size/1024/1024:.1f}MB). "
                        "Telegram limit is 50MB.\n"
                        f"You can download it directly from the website."
                    )
                    return
                
                with open(filepath, 'rb') as file:
                    await message.reply_document(
                        document=file,
                        caption=f"✅ {anime_title} - Episode {episode}",
                        filename=os.path.basename(filepath)
                    )
                
                logger.info(f"Sent file: {filepath}")
                
        except Exception as e:
            logger.error(f"Failed to send file: {e}")
            await message.reply_text(f"⚠️ Couldn't send file: {str(e)[:100]}")
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith("select:"):
            # Anime selected from search
            parts = query.data.split(":")
            if len(parts) >= 4:
                anime_code = parts[1]
                anime_title = parts[2]
                
                # Store in user context
                context.user_data['selected_anime'] = {
                    'code': anime_code,
                    'title': anime_title
                }
                
                await query.edit_message_text(
                    f"✅ Selected: *{anime_title}*\n\n"
                    "Now send me the episode number or range:\n"
                    "• Single episode: `5`\n"
                    "• Episode range: `1-10`\n"
                    "• Multiple episodes: `1,3,5`\n\n"
                    "Max 5 episodes at once.",
                    parse_mode='Markdown'
                )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.strip()
        
        # If user has selected anime and now sends episode range
        if 'selected_anime' in context.user_data:
            anime_info = context.user_data['selected_anime']
            
            # Parse episode range
            episodes = get_episodes(text)
            
            if episodes:
                # Limit to 5 episodes
                episodes = episodes[:5]
                
                user_id = update.effective_user.id
                
                # Check if user already has active download
                if user_id in self.user_sessions:
                    await update.message.reply_text("⚠️ You already have an active download. Use /cancel to cancel.")
                    return
                
                await update.message.reply_text(
                    f"📥 Downloading {len(episodes)} episode(s) of {anime_info['title']}..."
                )
                
                # Clear stored anime info
                del context.user_data['selected_anime']
                
                # Start download
                asyncio.create_task(
                    self.download_episodes(
                        user_id, 
                        anime_info['code'], 
                        anime_info['title'], 
                        episodes, 
                        update.message
                    )
                )
                return
            else:
                await update.message.reply_text(
                    "Invalid episode format. Use:\n"
                    "• Single: `5`\n"
                    "• Range: `1-10`\n"
                    "• Multiple: `1,3,5`"
                )
                return
        
        # Otherwise treat as search query
        context.args = [text]
        await self.search_command(update, context)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "❓ *Help - Anime Downloader Bot*\n\n"
            "*How to use:*\n"
            "1. Send me an anime name (or use /search)\n"
            "2. Select an anime from the results\n"
            "3. Send episode number or range\n"
            "4. Wait for downloads to complete\n\n"
            "*Commands:*\n"
            "/start - Show welcome message\n"
            "/search <name> - Search for anime\n"
            "/download <name> <episode> - Direct download\n"
            "/cancel - Cancel current download\n"
            "/help - This help message\n\n"
            "*Episode Formats:*\n"
            "• `5` - Single episode 5\n"
            "• `1-10` - Episodes 1 to 10\n"
            "• `1,3,5` - Specific episodes\n\n"
            "*Limitations:*\n"
            "• Max 5 episodes at once\n"
            "• Max 50MB per file (Telegram limit)\n"
            "• May require VPN for some regions",
            parse_mode='Markdown'
        )
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
            await update.message.reply_text("✅ Download cancelled.")
        else:
            await update.message.reply_text("📭 No active download to cancel.")
    
    def run(self):
        logger.info("Starting Alternative Anime Downloader Bot...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    # Get token
    token = os.getenv('BOT_TOKEN')
    if not token:
        print("Please set BOT_TOKEN environment variable")
        print("Or create a .env file with: BOT_TOKEN=your_token_here")
        token = input("Enter your bot token: ").strip()
    
    bot = AlternativeAnimeBot(token)
    bot.run()
