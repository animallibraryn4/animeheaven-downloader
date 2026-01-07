import os
import asyncio
import aiohttp
import aiofiles
import logging
from datetime import datetime
from typing import List, Dict, Optional
import subprocess
import shutil

from config import DOWNLOAD_SETTINGS, get_timestamp

logger = logging.getLogger(__name__)

class DownloadManager:
    def __init__(self):
        self.download_path = DOWNLOAD_SETTINGS['DEFAULT_DOWNLOAD_PATH']
        self.temp_path = DOWNLOAD_SETTINGS['TEMP_PATH']
        self.session = None
        
        # Create directories
        os.makedirs(self.download_path, exist_ok=True)
        os.makedirs(self.temp_path, exist_ok=True)
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def download_anime(self, anime_url: str, episodes: Optional[List[str]] = None, user_id: int = None):
        """Download anime episodes."""
        try:
            from .scraper import AnimeScraper
            
            async with AnimeScraper() as scraper:
                # Get anime info
                anime_info = await scraper.get_episodes_info(anime_url)
                if not anime_info:
                    raise Exception("Could not get anime information")
                
                # Determine which episodes to download
                if episodes is None:
                    # Download all available episodes
                    episodes_to_download = list(anime_info['episode_links'].keys())[:DOWNLOAD_SETTINGS.get('MAX_EPISODES_PER_REQUEST', 5)]
                else:
                    # Download selected episodes
                    episodes_to_download = []
                    for ep in episodes:
                        if ep in anime_info['episode_links']:
                            episodes_to_download.append(ep)
                
                if not episodes_to_download:
                    raise Exception("No episodes available for download")
                
                # Create user-specific directory
                timestamp = get_timestamp()
                user_dir = os.path.join(self.download_path, f"user_{user_id}_{timestamp}")
                os.makedirs(user_dir, exist_ok=True)
                
                downloaded_files = []
                failed_episodes = []
                
                # Download each episode
                for episode in episodes_to_download:
                    try:
                        episode_url = anime_info['episode_links'][episode]
                        
                        # Get download links for episode
                        download_links = await scraper.get_download_links(episode_url)
                        if not download_links:
                            failed_episodes.append(episode)
                            continue
                        
                        # Try to download from first available link
                        downloaded_file = await self.download_episode(
                            download_links[0]['url'],
                            episode,
                            user_dir
                        )
                        
                        if downloaded_file:
                            downloaded_files.append(downloaded_file)
                        else:
                            failed_episodes.append(episode)
                            
                        # Delay between downloads to avoid rate limiting
                        await asyncio.sleep(DOWNLOAD_SETTINGS.get('REQUEST_DELAY', 2))
                        
                    except Exception as e:
                        logger.error(f"Error downloading episode {episode}: {e}")
                        failed_episodes.append(episode)
                
                # Prepare result
                result = {
                    'anime_title': anime_url.split('/')[-1],
                    'episodes': ', '.join(episodes_to_download),
                    'downloaded_episodes': len(downloaded_files),
                    'failed_episodes': len(failed_episodes),
                    'total_size': self.calculate_total_size(downloaded_files),
                    'download_path': user_dir,
                    'files': downloaded_files,
                    'failed': failed_episodes
                }
                
                return result
                
        except Exception as e:
            logger.error(f"Download anime error: {e}")
            raise
    
    async def download_episode(self, video_url: str, episode: str, output_dir: str):
        """Download a single episode."""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            # Extract episode number
            ep_num = ''.join(filter(str.isdigit, episode)) or episode
            
            # Determine file extension
            if '.m3u8' in video_url:
                # HLS stream - need to use yt-dlp or similar
                return await self.download_hls_stream(video_url, ep_num, output_dir)
            else:
                # Direct download
                return await self.download_direct_file(video_url, ep_num, output_dir)
                
        except Exception as e:
            logger.error(f"Download episode error: {e}")
            return None
    
    async def download_direct_file(self, url: str, episode: str, output_dir: str):
        """Download a direct video file."""
        try:
            filename = f"Episode_{episode}.mp4"
            filepath = os.path.join(output_dir, filename)
            
            async with self.session.get(url) as response:
                if response.status != 200:
                    return None
                
                total_size = int(response.headers.get('content-length', 0))
                
                async with aiofiles.open(filepath, 'wb') as f:
                    downloaded = 0
                    
                    async for chunk in response.content.iter_chunked(1024 * 8):
                        await f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Log progress every 5MB
                        if total_size and downloaded % (5 * 1024 * 1024) < 1024 * 8:
                            percent = (downloaded / total_size) * 100
                            logger.info(f"Downloading {filename}: {percent:.1f}%")
            
            return filepath
            
        except Exception as e:
            logger.error(f"Direct download error: {e}")
            return None
    
    async def download_hls_stream(self, m3u8_url: str, episode: str, output_dir: str):
        """Download HLS stream using yt-dlp."""
        try:
            filename = f"Episode_{episode}.mp4"
            filepath = os.path.join(output_dir, filename)
            
            # Check if yt-dlp is available
            try:
                subprocess.run(['yt-dlp', '--version'], capture_output=True, check=True)
                yt_dlp_available = True
            except:
                yt_dlp_available = False
            
            if yt_dlp_available:
                # Use yt-dlp for best compatibility
                cmd = [
                    'yt-dlp',
                    '-o', filepath,
                    '--no-part',
                    '--merge-output-format', 'mp4',
                    m3u8_url
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0 and os.path.exists(filepath):
                    return filepath
            else:
                # Fallback to ffmpeg if available
                try:
                    subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
                    
                    cmd = [
                        'ffmpeg',
                        '-i', m3u8_url,
                        '-c', 'copy',
                        '-bsf:a', 'aac_adtstoasc',
                        filepath
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0 and os.path.exists(filepath):
                        return filepath
                except:
                    pass
            
            return None
            
        except Exception as e:
            logger.error(f"HLS download error: {e}")
            return None
    
    def calculate_total_size(self, files: List[str]) -> str:
        """Calculate total size of downloaded files."""
        total_bytes = 0
        
        for filepath in files:
            if os.path.exists(filepath):
                total_bytes += os.path.getsize(filepath)
        
        # Convert to human readable format
        for unit in ['B', 'KB', 'MB', 'GB']:
            if total_bytes < 1024.0:
                return f"{total_bytes:.2f} {unit}"
            total_bytes /= 1024.0
        
        return f"{total_bytes:.2f} TB"
    
    def cleanup_old_downloads(self, max_age_hours: int = 24):
        """Clean up downloads older than specified hours."""
        try:
            current_time = datetime.now().timestamp()
            
            for item in os.listdir(self.download_path):
                item_path = os.path.join(self.download_path, item)
                
                if os.path.isdir(item_path):
                    # Check directory age
                    dir_time = os.path.getctime(item_path)
                    age_hours = (current_time - dir_time) / 3600
                    
                    if age_hours > max_age_hours:
                        shutil.rmtree(item_path)
                        logger.info(f"Cleaned up old directory: {item}")
            
            logger.info("Cleanup completed")
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
