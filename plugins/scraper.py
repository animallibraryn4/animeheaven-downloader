import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup

from plugins.exceptions import RequestBlocked
from config import ANIMEHEAVEN_ABUSE_MSG, BLOCKED_TIMEOUT


class Scraper:
    """Animeheaven scraper using requests"""
    
    def __init__(self, anime: str):
        self.__anime = self.__convert_url(anime)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get(self, episode: str) -> list:
        """Return list of download links for given episode"""
        url = f'{self.__anime}{episode}'
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            # Check if blocked
            self.__is_blocked(response.text)
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for video sources
            video_sources = []
            
            # Method 1: Check for source tags
            for source in soup.find_all('source'):
                if source.get('src'):
                    video_sources.append(source['src'])
            
            # Method 2: Check for iframe embeds
            for iframe in soup.find_all('iframe'):
                if iframe.get('src'):
                    video_sources.append(iframe['src'])
            
            # Method 3: Check for video tags
            for video in soup.find_all('video'):
                if video.get('src'):
                    video_sources.append(video['src'])
            
            return video_sources if video_sources else None
            
        except Exception as e:
            print(f"Error scraping episode {episode}: {e}")
            return None
    
    def __is_blocked(self, html: str) -> bool:
        if html.find(ANIMEHEAVEN_ABUSE_MSG) != -1:
            raise RequestBlocked
        return False
    
    def __convert_url(self, url: str) -> str:
        """Convert anime overall preview url to episode url"""
        url_parsed = urlparse(url)
        return f'{url_parsed.scheme}://{url_parsed.netloc}/watch.php?{url_parsed.query}&e='
    
    def close(self):
        """Close the session"""
        self.session.close()
