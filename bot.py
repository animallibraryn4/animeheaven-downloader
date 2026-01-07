import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import asyncio
from datetime import datetime

from plugins.scraper import AnimeScraper
from plugins.downloader import DownloadManager
from helper.database import DatabaseManager

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class AnimeDownloaderBot:
    def __init__(self):
        self.token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.admin_id = int(os.getenv('ADMIN_ID', 0))
        
        # Initialize components
        self.scraper = AnimeScraper()
        self.downloader = DownloadManager()
        self.db = DatabaseManager()
        
        # User sessions
        self.user_states = {}
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send welcome message when /start is issued."""
        user = update.effective_user
        
        welcome_text = f"""
🤖 *Anime Downloader Bot*
Welcome {user.first_name}!

✨ *Available Commands:*
/search - Search for anime
/download - Download anime episodes
/my_downloads - View your download history
/help - Show help message

📌 *How to use:*
1. Use /search to find anime
2. Select from search results
3. Choose episodes to download
4. Get download links!

⚠️ *Note:* Please use responsibly and respect content creators.
"""
        keyboard = [
            [InlineKeyboardButton("🔍 Search Anime", callback_data="search")],
            [InlineKeyboardButton("📥 My Downloads", callback_data="my_downloads")],
            [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
    
    async def search_anime(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Initiate anime search."""
        await update.message.reply_text(
            "🔍 Please enter the anime name you want to search:"
        )
        self.user_states[update.effective_user.id] = 'waiting_for_search'
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle user messages based on state."""
        user_id = update.effective_user.id
        text = update.message.text
        
        if user_id not in self.user_states:
            return
        
        state = self.user_states[user_id]
        
        if state == 'waiting_for_search':
            await self.perform_search(update, context, text)
        elif state == 'waiting_for_episodes':
            await self.handle_episode_selection(update, context, text)
    
    async def perform_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: str):
        """Search for anime and display results."""
        await update.message.reply_text(f"🔎 Searching for *{query}*...", parse_mode='Markdown')
        
        try:
            results = await self.scraper.search_anime(query)
            
            if not results:
                await update.message.reply_text("❌ No results found. Try a different search term.")
                return
            
            # Store results in context for this user
            context.user_data['search_results'] = results
            
            # Create inline keyboard with results
            keyboard = []
            for i, anime in enumerate(results[:10]):  # Show first 10 results
                keyboard.append([
                    InlineKeyboardButton(
                        f"{anime['title']} ({anime.get('year', 'N/A')})",
                        callback_data=f"select_{i}"
                    )
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                f"📺 *Found {len(results)} results:*\nSelect an anime:",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            await update.message.reply_text("❌ An error occurred during search. Please try again.")
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id
        
        if data == "search":
            await query.message.reply_text("🔍 Enter anime name to search:")
            self.user_states[user_id] = 'waiting_for_search'
            
        elif data == "my_downloads":
            await self.show_user_downloads(query, context)
            
        elif data == "help":
            await self.show_help(query)
            
        elif data.startswith("select_"):
            await self.select_anime(query, context, data)
            
        elif data.startswith("download_"):
            await self.start_download(query, context, data)
            
        elif data.startswith("episode_"):
            await self.select_episode_range(query, context, data)
    
    async def select_anime(self, query, context, data):
        """Handle anime selection from search results."""
        try:
            index = int(data.split("_")[1])
            results = context.user_data.get('search_results', [])
            
            if index >= len(results):
                await query.message.reply_text("❌ Invalid selection.")
                return
            
            selected = results[index]
            
            # Store selected anime
            context.user_data['selected_anime'] = selected
            
            # Get episodes info
            episodes_info = await self.scraper.get_episodes_info(selected['url'])
            
            if not episodes_info:
                await query.message.reply_text("❌ Could not fetch episodes information.")
                return
            
            total_episodes = episodes_info.get('total_episodes', 'Unknown')
            available = episodes_info.get('available_episodes', [])
            
            keyboard = [
                [InlineKeyboardButton("📥 Download All", callback_data=f"download_all")],
                [InlineKeyboardButton("📋 Select Episodes", callback_data=f"episode_select")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            info_text = f"""
🎬 *{selected['title']}*

📊 *Information:*
• Total Episodes: {total_episodes}
• Available: {len(available)} episodes
• Year: {selected.get('year', 'N/A')}
• Status: {selected.get('status', 'Unknown')}

Choose what you want to download:
"""
            await query.message.reply_text(
                info_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Selection error: {e}")
            await query.message.reply_text("❌ An error occurred.")
    
    async def start_download(self, query, context, data):
        """Start download process."""
        await query.message.reply_text("⏳ Starting download... Please wait.")
        
        try:
            anime = context.user_data.get('selected_anime')
            if not anime:
                await query.message.reply_text("❌ No anime selected. Please search again.")
                return
            
            if data == "download_all":
                # Download all episodes
                episodes = None
            else:
                # Get specific episodes
                episodes = context.user_data.get('selected_episodes', [])
            
            # Start download
            download_info = await self.downloader.download_anime(
                anime['url'],
                episodes,
                query.from_user.id
            )
            
            # Save to database
            self.db.save_download(
                user_id=query.from_user.id,
                anime_title=anime['title'],
                episodes=download_info['episodes'],
                download_path=download_info['path']
            )
            
            # Send download info to user
            await self.send_download_complete(query, download_info)
            
        except Exception as e:
            logger.error(f"Download error: {e}")
            await query.message.reply_text(f"❌ Download failed: {str(e)}")
    
    async def send_download_complete(self, query, download_info):
        """Send download completion message with files."""
        message_text = f"""
✅ *Download Complete!*

📁 *Details:*
• Anime: {download_info['anime_title']}
• Episodes: {download_info['episodes']}
• Total Size: {download_info['total_size']}
• Status: Ready for download
"""
        await query.message.reply_text(message_text, parse_mode='Markdown')
        
        # Send files (in batches if multiple)
        files = download_info['files']
        for file_path in files:
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'rb') as f:
                        await query.message.reply_document(
                            document=f,
                            filename=os.path.basename(file_path)
                        )
                except Exception as e:
                    logger.error(f"Error sending file: {e}")
                    await query.message.reply_text(f"❌ Could not send file: {os.path.basename(file_path)}")
    
    async def show_user_downloads(self, query, context):
        """Show user's download history."""
        user_id = query.from_user.id
        downloads = self.db.get_user_downloads(user_id)
        
        if not downloads:
            await query.message.reply_text("📭 You haven't downloaded anything yet.")
            return
        
        text = "📥 *Your Downloads:*\n\n"
        for dl in downloads[:10]:  # Show last 10 downloads
            text += f"• *{dl['anime_title']}*\n"
            text += f"  Episodes: {dl['episodes']}\n"
            text += f"  Date: {dl['download_date']}\n\n"
        
        await query.message.reply_text(text, parse_mode='Markdown')
    
    async def show_help(self, query):
        """Show help message."""
        help_text = """
❓ *Help - Anime Downloader Bot*

*Available Commands:*
/start - Start the bot
/search - Search for anime
/download - Start download process
/my_downloads - View your download history

*How to Use:*
1. Use /search to find anime
2. Select from the results
3. Choose episodes to download
4. Get your files directly!

*Tips:*
• Use specific search terms for better results
• Check episode availability before downloading
• Files are sent as documents via Telegram

⚠️ *Disclaimer:*
This bot is for educational purposes. Please respect content creators and copyright laws.
"""
        await query.message.reply_text(help_text, parse_mode='Markdown')
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors."""
        logger.error(f"Update {update} caused error {context.error}")
        
        try:
            if update.effective_message:
                await update.effective_message.reply_text(
                    "❌ An error occurred. Please try again later."
                )
        except:
            pass
    
    def run(self):
        """Run the bot."""
        if not self.token:
            logger.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
            return
        
        # Create application
        application = Application.builder().token(self.token).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("search", self.search_anime))
        application.add_handler(CommandHandler("my_downloads", self.show_user_downloads))
        application.add_handler(CommandHandler("help", self.show_help))
        
        application.add_handler(CallbackQueryHandler(self.button_handler))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        application.add_error_handler(self.error_handler)
        
        # Start bot
        logger.info("Bot is starting...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

# Run the bot
if __name__ == '__main__':
    bot = AnimeDownloaderBot()
    bot.run()
