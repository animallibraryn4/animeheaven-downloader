import requests
import re
import json
from typing import Dict, List, Optional
from urllib.parse import quote, urlparse

from bs4 import BeautifulSoup

# Change to (if using relative import within plugins directory):
from .exceptions import SourceError, NoResultsFound


class BaseScraper:
    """Base class for all anime scrapers"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
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
    """Scraper for GogoAnime"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://gogoanime3.co"
        self.search_url = f"{self.base_url}/search.html"
    
    def search(self, query: str) -> List[Dict]:
        """Search anime on GogoAnime"""
        try:
            params = {'keyword': query}
            response = self.session.get(self.search_url, params=params, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            for item in soup.select('ul.items li'):
                try:
                    title_elem = item.select_one('p.name a')
                    if not title_elem:
                        continue
                    
                    anime_id = title_elem['href'].replace('/', '').replace('category', '')
                    title = title_elem.text.strip()
                    url = f"{self.base_url}{title_elem['href']}"
                    
                    # Get released year
                    released_elem = item.select_one('p.released')
                    released = released_elem.text.strip() if released_elem else "N/A"
                    
                    results.append({
                        'id': anime_id,
                        'title': title,
                        'url': url,
                        'released': released,
                        'source': 'gogoanime'
                    })
                except Exception as e:
                    print(f"Error parsing search result: {e}")
                    continue
            
            return results
            
        except Exception as e:
            raise SourceError(f"Search failed: {str(e)}")
    
    def get_episodes(self, anime_id: str) -> List[Dict]:
        """Get all episodes for an anime"""
        try:
            url = f"{self.base_url}/category/{anime_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Get total episodes
            episode_range = soup.select_one('#episode_page li:last-child a')
            if episode_range:
                last_ep = episode_range['ep_end']
                total_episodes = int(last_ep)
                
                episodes = []
                for ep_num in range(1, total_episodes + 1):
                    episodes.append({
                        'number': ep_num,
                        'id': f"{anime_id}-episode-{ep_num}",
                        'url': f"{self.base_url}/{anime_id}-episode-{ep_num}"
                    })
                
                return episodes
            
            return []
            
        except Exception as e:
            raise SourceError(f"Failed to get episodes: {str(e)}")
    
    def get_download_links(self, episode_id: str) -> List[Dict]:
        """Get download/video links for an episode"""
        try:
            url = f"{self.base_url}/{episode_id}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for video iframes
            iframe = soup.select_one('iframe')
            if iframe and iframe.get('src'):
                # This returns the embed URL, which might need further processing
                return [{
                    'url': iframe['src'],
                    'quality': 'Unknown',
                    'type': 'iframe'
                }]
            
            # Alternative: Look for download links
            download_links = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                if any(ext in href for ext in ['.mp4', '.m3u8', '.mkv', '.avi']):
                    quality = link.text.strip() or 'Unknown'
                    download_links.append({
                        'url': href if href.startswith('http') else f"{self.base_url}{href}",
                        'quality': quality,
                        'type': 'direct'
                    })
            
            return download_links
            
        except Exception as e:
            raise SourceError(f"Failed to get download links: {str(e)}")


class AnimePaheScraper(BaseScraper):
    """Scraper for AnimePahe (has better quality and direct links)"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://animepahe.com"
        self.api_url = f"{self.base_url}/api"
    
    def search(self, query: str) -> List[Dict]:
        try:
            params = {'q': query}
            response = self.session.get(f"{self.base_url}/api", params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            for item in data.get('data', []):
                results.append({
                    'id': str(item['id']),
                    'title': item['title'],
                    'url': f"{self.base_url}/anime/{item['session']}",
                    'released': str(item.get('year', 'N/A')),
                    'source': 'animepahe'
                })
            
            return results
            
        except Exception as e:
            raise SourceError(f"AnimePahe search failed: {str(e)}")


class MultiSourceScraper:
    """Main scraper that supports multiple sources"""
    
    def __init__(self, source: str = 'gogoanime'):
        self.source = source
        self.scrapers = {
            'gogoanime': GogoAnimeScraper(),
            'animepahe': AnimePaheScraper()
        }
        self.current_scraper = self.scrapers.get(source)
        if not self.current_scraper:
            self.current_scraper = self.scrapers['gogoanime']
    
    def search(self, query: str) -> List[Dict]:
        return self.current_scraper.search(query)
    
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


# Alternative: Direct video extractor from common streaming sites
class DirectVideoExtractor:
    """Extract direct video links from various streaming sites"""
    
    @staticmethod
    def extract_from_url(url: str) -> Optional[str]:
        """Try to extract direct video URL from various sources"""
        try:
            # For GogoAnime embeds
            if 'gogoanime' in url or 'goload' in url:
                return DirectVideoExtractor.extract_gogoanime(url)
            
            # For MP4Upload
            elif 'mp4upload' in url:
                return DirectVideoExtractor.extract_mp4upload(url)
            
            # For Streamtape
            elif 'streamtape' in url:
                return DirectVideoExtractor.extract_streamtape(url)
            
            # For other direct video links
            elif any(ext in url for ext in ['.mp4', '.m3u8', '.mkv']):
                return url
                
        except Exception as e:
            print(f"Extraction failed: {e}")
        
        return None
    
    @staticmethod
    def extract_gogoanime(embed_url: str) -> Optional[str]:
        """Extract video from GogoAnime embed"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://gogoanime3.co/'
            }
            
            response = requests.get(embed_url, headers=headers, timeout=10)
            
            # Look for video sources in the embed
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Check for video tag
            video = soup.find('video')
            if video and video.get('src'):
                return video['src']
            
            # Check for source tag inside video
            source = soup.find('source')
            if source and source.get('src'):
                return source['src']
            
            # Look for hidden video URLs in JavaScript
            script_text = str(soup.find_all('script'))
            patterns = [
                r'sources:\s*\[.*?file:\s*["\'](.*?)["\']',
                r'file:\s*["\'](.*?)["\']',
                r'src:\s*["\'](.*?)["\']',
                r'"(https?://[^"]+\.(?:mp4|m3u8|mkv)[^"]*)"'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, script_text, re.DOTALL | re.IGNORECASE)
                if match:
                    url = match.group(1)
                    if any(ext in url for ext in ['.mp4', '.m3u8', '.mkv']):
                        return url
            
        except Exception as e:
            print(f"GogoAnime extraction error: {e}")
        
        return None
    
    @staticmethod
    def extract_mp4upload(url: str) -> Optional[str]:
        """Extract from MP4Upload"""
        try:
            response = requests.get(url, timeout=10)
            match = re.search(r'src:\s*["\'](.*?\.mp4)["\']', response.text)
            if match:
                return match.group(1)
        except:
            pass
        return None
    
    @staticmethod
    def extract_streamtape(url: str) -> Optional[str]:
        """Extract from Streamtape"""
        try:
            response = requests.get(url, timeout=10)
            match = re.search(r'getElementById\(\'ideoo\'\)\.src = "(.*?)"', response.text)
            if match:
                video_url = match.group(1)
                if not video_url.startswith('http'):
                    video_url = 'https:' + video_url
                return video_url
        except:
            pass
        return None
