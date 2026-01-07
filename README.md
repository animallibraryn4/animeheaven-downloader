# Anime Downloader Telegram Bot 🤖

A simple Telegram bot for downloading anime episodes directly through Telegram.

## Features ✨
- 🔍 Search anime by name
- 📥 Download multiple episodes
- 📊 Download history tracking
- ⚡ Fast and efficient downloads
- 📱 Easy to use Telegram interface

## Quick Deploy 🚀

### 1. On Koyeb (Easiest)
1. Fork this repository
2. Go to [Koyeb Dashboard](https://app.koyeb.com/)
3. Click "Create App" → "Deploy from GitHub"
4. Select your forked repository
5. Add environment variables from `.env.example`
6. Click "Deploy"

### 2. On Google Colab
```python
!pip install python-telegram-bot aiohttp beautifulsoup4 python-dotenv
!git clone https://github.com/yourusername/anime-downloader-bot
%cd anime-downloader-bot

# Set up environment
import os
os.environ['TELEGRAM_BOT_TOKEN'] = 'YOUR_BOT_TOKEN'

# Run the bot
!python bot.py```
