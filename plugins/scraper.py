import aiohttp
import asyncio
from bs4 import BeautifulSoup
import logging
import re
from urllib.parse import quote, urljoin
import json

from config import ANIME_SOURCES

logger = logging.getLogger(__name__)

class AnimeScraper:
    def __init__(self, source='gogoanime'):
        self.source_config = ANIME_SOURCES.get(source, ANIME_SOURCES['gogoanime'])
        self.base_url = self.source_config['base_url']
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def search_anime(self, query: str):
        """Search for anime by name."""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            search_url = f"{self.base_url}/search.html"
            params = {'keyword': query}
            
            async with self.session.get(search_url, params=params) as response:
                if response.status != 200:
                    return []
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                results = []
                
                # Parse search results (adjust selectors based on source)
                if 'gogoanime' in self.base_url:
                    items = soup.select('ul.items li')
                    for item in items:
                        title_elem = item.select_one('p.name a')
                        if title_elem:
                            anime_data = {
                                'title': title_elem.get('title', '').strip(),
                                'url': urljoin(self.base_url, title_elem.get('href', '')),
                                'image': item.select_one('img').get('src', '') if item.select_one('img') else '',
                                'year': item.select_one('p.released').text.strip().replace('Released: ', '') if item.select_one('p.released') else 'N/A',
                                'status': 'Completed' if item.select_one('.ongoing') and 'Completed' in item.select_one('.ongoing').text else 'Ongoing'
                            }
                            results.append(anime_data)
                
                return results[:15]  # Limit results
                
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    async def get_episodes_info(self, anime_url: str):
        """Get information about available episodes."""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            async with self.session.get(anime_url) as response:
                if response.status != 200:
                    return None
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                episodes_info = {
                    'total_episodes': 0,
                    'available_episodes': [],
                    'episode_links': {}
                }
                
                # Parse episodes (adjust selectors based on source)
                if 'gogoanime' in self.base_url:
                    # Get total episodes
                    ep_range = soup.select_one('.anime_video_body_cate .type')
                    if ep_range:
                        match = re.search(r'Episodes:\s*(\d+)', ep_range.text)
                        if match:
                            episodes_info['total_episodes'] = int(match.group(1))
                    
                    # Get episode list
                    ep_list = soup.select('#episode_related li a')
                    for ep in ep_list:
                        ep_num = ep.select_one('.name').text.strip() if ep.select_one('.name') else ''
                        ep_link = urljoin(self.base_url, ep.get('href', ''))
                        
                        if ep_num and ep_link:
                            episodes_info['available_episodes'].append(ep_num)
                            episodes_info['episode_links'][ep_num] = ep_link
                
                return episodes_info
                
        except Exception as e:
            logger.error(f"Episodes info error: {e}")
            return None
    
    async def get_download_links(self, episode_url: str):
        """Get download links for a specific episode."""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            async with self.session.get(episode_url) as response:
                if response.status != 200:
                    return []
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                download_links = []
                
                # Parse download links (adjust selectors based on source)
                if 'gogoanime' in self.base_url:
                    # Look for download server options
                    servers = soup.select('.anime_muti_link ul li a')
                    for server in servers:
                        server_name = server.text.strip()
                        server_data = server.get('data-video', '')
                        
                        if server_data and server_data.startswith('http'):
                            download_links.append({
                                'server': server_name,
                                'url': server_data,
                                'quality': 'Unknown'
                            })
                
                return download_links
                
        except Exception as e:
            logger.error(f"Download links error: {e}")
            return []
    
    async def get_direct_download_url(self, video_page_url: str):
        """Extract direct download URL from video page."""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession()
            
            # First get the video page
            async with self.session.get(video_page_url) as response:
                if response.status != 200:
                    return None
                
                html = await response.text()
                
                # Try to extract video URL from page
                # This pattern might need adjustment based on the source
                patterns = [
                    r'sources:\s*\[\s*\{\s*src:\s*["\']([^"\']+)["\']',
                    r'file:\s*["\']([^"\']+\.(mp4|m3u8))["\']',
                    r'video_url\s*=\s*["\']([^"\']+)["\']'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, html, re.IGNORECASE)
                    if match:
                        return match.group(1)
                
                return None
                
        except Exception as e:
            logger.error(f"Direct URL error: {e}")
            return None
