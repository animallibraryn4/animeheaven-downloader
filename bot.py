import os
import sys
import logging
import asyncio
from typing import Dict, List, Optional
import tempfile

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, ContextTypes, filters
)

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import BOT_TOKEN, ANIME_SOURCES, DEFAULT_SOURCE, MAX_DOWNLOADS_PER_USER
from plugins.scraper import MultiSourceScraper, DirectVideoExtractor
from plugins.downloader import SmartDownloader
from plugins.exceptions import SourceError, NoResultsFound

logger = logging.getLogger(__name__)

class AnimeDownloaderBot:
    def __init__(self):
        self.app = Application.builder().token(BOT_TOKEN).build()
        self.user_sessions: Dict[int, Dict] = {}
        self.scraper = MultiSourceScraper(DEFAULT_SOURCE)
        self.setup_handlers()
    
    def setup_handlers(self):
        """Setup all command handlers"""
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("help", self.help_command))
        self.app.add_handler(CommandHandler("search", self.search_command))
        self.app.add_handler(CommandHandler("download", self.download_command))
        self.app.add_handler(CommandHandler("sources", self.sources_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("cancel", self.cancel_command))
        
        # Callback handlers
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Message handlers
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Error handler
        self.app.add_error_handler(self.error_handler)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Welcome message"""
        user = update.effective_user
        welcome_msg = f"""
🎬 *Anime Downloader Bot*

Hello {user.first_name}! I can help you download anime episodes from multiple sources.

*Available Commands:*
/search - Search for anime
/download - Download episodes
/sources - Change download source
/status - Check download status
/cancel - Cancel download
/help - Show help

*Supported Sources:* GogoAnime, AnimePahe

*Note:* Downloads are sent as Telegram files (max 50MB).
        """
        await update.message.reply_text(welcome_msg, parse_mode='Markdown')
    
    async def search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Search for anime"""
        if not context.args:
            await update.message.reply_text("Please provide search query:\n`/search Naruto`", parse_mode='Markdown')
            return
        
        query = ' '.join(context.args)
        await update.message.reply_text(f"🔍 Searching for '{query}'...")
        
        try:
            results = self.scraper.search(query)
            
            if not results:
                await update.message.reply_text("❌ No results found.")
                return
            
            # Limit to first 10 results
            results = results[:10]
            
            # Create inline keyboard with results
            keyboard = []
            for result in results:
                btn_text = f"{result['title']} ({result['released']})"
                callback_data = f"select:{result['id']}:{result['source']}"
                keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback_data)])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"📋 Found {len(results)} results:\n",
                reply_markup=reply_markup
            )
            
        except Exception as e:
            await update.message.reply_text(f"❌ Search failed: {str(e)[:100]}")
    
    async def download_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Download anime by ID"""
        if len(context.args) < 2:
            await update.message.reply_text(
                "Usage: `/download <anime_id> <episode_range>`\n"
                "Example: `/download naruto-123 1-10`\n\n"
                "Get anime_id from /search results.",
                parse_mode='Markdown'
            )
            return
        
        anime_id = context.args[0]
        episode_range = context.args[1]
        
        # Parse episode range
        episodes = self.parse_episode_range(episode_range)
        if not episodes:
            await update.message.reply_text("Invalid episode range. Use format: 1-10 or 5")
            return
        
        user_id = update.effective_user.id
        
        # Check download limit
        if user_id in self.user_sessions:
            await update.message.reply_text("⚠️ You already have an active download.")
            return
        
        await update.message.reply_text(f"📥 Downloading {len(episodes)} episode(s)...")
        
        # Start download
        asyncio.create_task(
            self.download_episodes(user_id, anime_id, episodes, update.message)
        )
    
    async def download_episodes(self, user_id: int, anime_id: str, episodes: List[int], message):
        """Download multiple episodes"""
        try:
            self.user_sessions[user_id] = {
                'status': 'downloading',
                'current': 0,
                'total': len(episodes),
                'failed': []
            }
            
            downloader = SmartDownloader()
            
            for ep_num in episodes:
                self.user_sessions[user_id]['current'] = ep_num
                
                try:
                    # Get download links for episode
                    episode_id = f"{anime_id}-episode-{ep_num}"
                    links = self.scraper.get_download_links(episode_id)
                    
                    if not links:
                        await message.reply_text(f"❌ No links found for episode {ep_num}")
                        self.user_sessions[user_id]['failed'].append(ep_num)
                        continue
                    
                    # Try each link until one works
                    downloaded = False
                    for link in links:
                        await message.reply_text(f"⬇️ Downloading Episode {ep_num}...")
                        
                        # Try to extract direct video URL
                        direct_url = DirectVideoExtractor.extract_from_url(link['url'])
                        if not direct_url:
                            direct_url = link['url']
                        
                        # Download the file
                        filename = f"Episode_{ep_num}.mp4"
                        filepath = downloader.download(direct_url, filename)
                        
                        if filepath:
                            # Send to user
                            await self.send_file_to_user(message, filepath, ep_num)
                            downloaded = True
                            break
                    
                    if not downloaded:
                        await message.reply_text(f"❌ Failed to download episode {ep_num}")
                        self.user_sessions[user_id]['failed'].append(ep_num)
                    
                except Exception as e:
                    logger.error(f"Error downloading episode {ep_num}: {e}")
                    self.user_sessions[user_id]['failed'].append(ep_num)
            
            # Cleanup
            downloader.cleanup()
            
            # Send summary
            failed_count = len(self.user_sessions[user_id]['failed'])
            success_count = len(episodes) - failed_count
            
            summary = f"""
✅ Download Complete!

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
    
    async def send_file_to_user(self, message, filepath: str, episode: int):
        """Send downloaded file to user"""
        try:
            if os.path.exists(filepath):
                file_size = os.path.getsize(filepath)
                
                if file_size > 50 * 1024 * 1024:
                    await message.reply_text(
                        f"⚠️ Episode {episode} is too large ({file_size/1024/1024:.1f}MB). "
                        "Telegram limit is 50MB."
                    )
                    return
                
                with open(filepath, 'rb') as file:
                    await message.reply_document(
                        document=file,
                        caption=f"✅ Episode {episode}",
                        filename=f"Episode_{episode}.mp4"
                    )
                
                # Delete file
                os.remove(filepath)
                
        except Exception as e:
            logger.error(f"Failed to send file: {e}")
    
    async def sources_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Change download source"""
        keyboard = []
        for source_name in ANIME_SOURCES.keys():
            keyboard.append([
                InlineKeyboardButton(
                    f"🌐 {source_name.title()}",
                    callback_data=f"source:{source_name}"
                )
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Select download source:",
            reply_markup=reply_markup
        )
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check download status"""
        user_id = update.effective_user.id
        
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            status_msg = f"""
📊 Download Status

Current: Episode {session['current']}
Total: {session['total']} episodes
Status: {session['status'].title()}
Failed: {len(session['failed'])} episodes
            """
            await update.message.reply_text(status_msg)
        else:
            await update.message.reply_text("📭 No active downloads.")
    
    async def cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel download"""
        user_id = update.effective_user.id
        
        if user_id in self.user_sessions:
            del self.user_sessions[user_id]
            await update.message.reply_text("❌ Download cancelled.")
        else:
            await update.message.reply_text("📭 No active download to cancel.")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button clicks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data.startswith("select:"):
            # Anime selected from search
            parts = data.split(":")
            if len(parts) >= 3:
                anime_id = parts[1]
                source = parts[2]
                
                self.scraper.set_source(source)
                
                await query.edit_message_text(
                    f"Selected anime ID: `{anime_id}`\n\n"
                    "Now send episode range:\n"
                    "`1-10` for episodes 1 to 10\n"
                    "`5` for single episode\n"
                    "`1,3,5` for specific episodes",
                    parse_mode='Markdown'
                )
                
                # Store anime_id in context
                context.user_data['selected_anime'] = anime_id
        
        elif data.startswith("source:"):
            # Source selected
            source = data.split(":")[1]
            self.scraper.set_source(source)
            await query.edit_message_text(f"✅ Source changed to: {source.title()}")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages"""
        text = update.message.text
        
        # If user has selected anime and now sends episode range
        if 'selected_anime' in context.user_data:
            anime_id = context.user_data['selected_anime']
            episodes = self.parse_episode_range(text)
            
            if episodes:
                # Start download
                user_id = update.effective_user.id
                
                if user_id in self.user_sessions:
                    await update.message.reply_text("⚠️ You already have an active download.")
                    return
                
                await update.message.reply_text(f"📥 Downloading {len(episodes)} episode(s)...")
                
                # Clear stored anime_id
                del context.user_data['selected_anime']
                
                # Start download
                asyncio.create_task(
                    self.download_episodes(user_id, anime_id, episodes, update.message)
                )
                return
        
        # Otherwise treat as search query
        await self.search_command(update, context)
    
    def parse_episode_range(self, text: str) -> List[int]:
        """Parse episode range text into list of episode numbers"""
        try:
            episodes = []
            
            # Remove spaces and split by commas
            parts = text.replace(' ', '').split(',')
            
            for part in parts:
                if '-' in part:
                    # Range like 1-10
                    start, end = map(int, part.split('-'))
                    episodes.extend(range(start, end + 1))
                else:
                    # Single episode
                    episodes.append(int(part))
            
            # Remove duplicates and sort
            episodes = sorted(set(episodes))
            
            # Limit to 10 episodes max
            return episodes[:10]
            
        except:
            return []
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Exception while handling an update: {context.error}")
        
        try:
            if update and update.effective_message:
                await update.effective_message.reply_text(
                    "❌ An error occurred. Please try again."
                )
        except:
            pass
    
    def run(self):
        """Start the bot"""
        logger.info("Starting Anime Downloader Bot...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)
