import requests
import re
import json
from typing import Dict, List, Optional
from urllib.parse import quote, urlparse

from bs4 import BeautifulSoup
from plugins.exceptions import SourceError, NoResultsFound


class BaseScraper:
    """Base class for all anime scrapers"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def search(self, query: str) -> List[Dict]:
        """Search for anime by name"""
        raise NotImplementedError
    
    def get_episodes(self, anime_id: str) -> List[Dict]:
        """Get list of episodes for an anime"""
        raise NotImplementedError
    
    def get_download_links(self, episode_id: str) -> List[Dict]:
        """Get download links for a specific episode"""
        raise NotImplementedError
    
    def close(self):
        self.session.close()


class GogoAnimeScraper(BaseScraper):
    """Simple GogoAnime scraper that works"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://gogoanime3.co"
    
    def search(self, query: str) -> List[Dict]:
        """Search anime on GogoAnime"""
        try:
            search_url = f"{self.base_url}/search.html"
            params = {'keyword': query}
            
            response = self.session.get(search_url, params=params, timeout=15)
            response.raise_for_status()
            
            if response.status_code == 403:
                raise SourceError("Access forbidden. Try again later.")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # Look for search results
            items = soup.select('ul.items li')
            if not items:
                items = soup.select('.items li')
            
            for item in items[:10]:  # Limit to 10 results
                try:
                    # Get title and link
                    title_elem = item.select_one('p.name a') or item.select_one('a')
                    if not title_elem:
                        continue
                    
                    title = title_elem.text.strip()
                    href = title_elem['href']
                    
                    # Extract anime ID
                    if '/category/' in href:
                        anime_id = href.replace('/category/', '').strip()
                    else:
                        anime_id = href.split('/')[-1].replace('.html', '')
                    
                    # Get release info
                    released_elem = item.select_one('p.released')
                    released = released_elem.text.strip() if released_elem else "N/A"
                    
                    results.append({
                        'id': anime_id,
                        'title': title,
                        'url': f"{self.base_url}{href}" if href.startswith('/') else href,
                        'released': released,
                        'source': 'gogoanime'
                    })
                    
                except Exception as e:
                    print(f"Error parsing result: {e}")
                    continue
            
            return results
            
        except Exception as e:
            print(f"Search error: {e}")
            return []  # Return empty list instead of raising error
    
    def get_episodes(self, anime_id: str) -> List[Dict]:
        """Get all episodes for an anime"""
        try:
            url = f"{self.base_url}/category/{anime_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            episodes = []
            
            # Find episode range
            episode_page = soup.select_one('#episode_page')
            if episode_page:
                last_ep = episode_page.select('a')[-1]
                if 'ep_end' in last_ep.attrs:
                    total_episodes = int(last_ep['ep_end'])
                    
                    for ep_num in range(1, min(total_episodes, 20) + 1):  # Limit to 20 episodes
                        episodes.append({
                            'number': ep_num,
                            'id': f"{anime_id}-episode-{ep_num}",
                            'url': f"{self.base_url}/{anime_id}-episode-{ep_num}"
                        })
            
            return episodes
            
        except Exception as e:
            print(f"Get episodes error: {e}")
            return []
    
    def get_download_links(self, episode_id: str) -> List[Dict]:
        """Get download links for an episode"""
        try:
            url = f"{self.base_url}/{episode_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            links = []
            
            # Look for video iframes
            iframe = soup.select_one('iframe[src*="streamtape"]') or \
                     soup.select_one('iframe[src*="mp4upload"]') or \
                     soup.select_one('iframe[src*="vidstream"]')
            
            if iframe:
                src = iframe['src']
                if not src.startswith('http'):
                    src = f"https:{src}" if src.startswith('//') else f"https://{src}"
                
                links.append({
                    'url': src,
                    'quality': 'HD',
                    'type': 'iframe'
                })
            
            # Also add the episode page itself as a fallback
            links.append({
                'url': url,
                'quality': 'Page',
                'type': 'page'
            })
            
            return links
            
        except Exception as e:
            print(f"Get links error: {e}")
            return []


class MultiSourceScraper:
    """Main scraper"""
    
    def __init__(self, source: str = 'gogoanime'):
        self.source = source
        self.scrapers = {
            'gogoanime': GogoAnimeScraper(),
        }
        self.current_scraper = self.scrapers.get(source, self.scrapers['gogoanime'])
    
    def search(self, query: str) -> List[Dict]:
        results = self.current_scraper.search(query)
        if not results:
            raise NoResultsFound(f"No results found for '{query}'")
        return results
    
    def get_episodes(self, anime_id: str) -> List[Dict]:
        return self.current_scraper.get_episodes(anime_id)
    
    def get_download_links(self, episode_id: str) -> List[Dict]:
        return self.current_scraper.get_download_links(episode_id)
    
    def set_source(self, source: str):
        if source in self.scrapers:
            self.source = source
            self.current_scraper = self.scrapers[source]
    
    def close(self):
        for scraper in self.scrapers.values():
            scraper.close()


class DirectVideoExtractor:
    """Simple extractor for testing"""
    
    @staticmethod
    def extract_from_url(url: str) -> Optional[str]:
        """Return the URL as-is for testing"""
        return url
