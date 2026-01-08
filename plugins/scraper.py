import requests
import re
import json
from typing import Dict, List, Optional
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup

class SourceError(Exception):
    pass

class NoResultsFound(Exception):
    pass


class AnimeHeavenScraper:
    """Simple scraper for AnimeHeaven.me"""
    
    def __init__(self):
        self.base_url = "https://animeheaven.me"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://animeheaven.me/',
            'Origin': 'https://animeheaven.me'
        })
    
    def search(self, query: str) -> List[Dict]:
        """Search anime on AnimeHeaven"""
        print(f"DEBUG: Searching for '{query}'")
        
        try:
            # AnimeHeaven search endpoint
            search_url = f"{self.base_url}/search.php"
            
            # Prepare form data
            form_data = {
                'q': query,
                'search': 'Search'
            }
            
            print(f"DEBUG: Sending POST request to {search_url}")
            response = self.session.post(search_url, data=form_data, timeout=30)
            print(f"DEBUG: Response status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"DEBUG: Bad response: {response.status_code}")
                return []
            
            # Check for abuse protection
            if 'abuse protection' in response.text.lower():
                print("DEBUG: Abuse protection detected")
                return []
            
            # Save response for debugging
            with open('debug_search.html', 'w', encoding='utf-8') as f:
                f.write(response.text[:5000])  # Save first 5000 chars
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # METHOD 1: Look for anime grid items
            print("DEBUG: Looking for anime grid items...")
            anime_items = soup.select('div.video, .anime-item, .item, [class*="anime"]')
            print(f"DEBUG: Found {len(anime_items)} potential items")
            
            for item in anime_items[:20]:
                try:
                    # Find link in the item
                    link = item.find('a')
                    if not link or not link.get('href'):
                        continue
                    
                    href = link['href']
                    if 'anime.php' not in href:
                        continue
                    
                    # Extract anime code
                    if '?' in href:
                        anime_code = href.split('?')[1]
                    else:
                        anime_code = href.split('/')[-1]
                    
                    # Get title
                    title = link.get('title', '') or link.text.strip()
                    
                    # Clean title
                    title = ' '.join(title.split())
                    if not title or len(title) < 2:
                        continue
                    
                    # Get image if available
                    img = link.find('img') or item.find('img')
                    image_url = img['src'] if img and img.get('src') else ''
                    
                    results.append({
                        'id': anime_code,
                        'title': title[:100],
                        'url': urljoin(self.base_url, href),
                        'image': image_url,
                        'released': 'Unknown',
                        'source': 'animeheaven'
                    })
                    
                except Exception as e:
                    continue
            
            # METHOD 2: If no results, try finding all anime.php links
            if not results:
                print("DEBUG: Method 1 failed, trying Method 2...")
                all_links = soup.find_all('a', href=True)
                anime_links = [link for link in all_links if 'anime.php' in link['href']]
                print(f"DEBUG: Found {len(anime_links)} anime.php links")
                
                for link in anime_links[:15]:
                    try:
                        href = link['href']
                        
                        # Extract anime code
                        if '?' in href:
                            anime_code = href.split('?')[1]
                        else:
                            anime_code = href.split('/')[-1]
                        
                        title = link.get('title', '') or link.text.strip()
                        title = ' '.join(title.split())
                        
                        if title and len(title) > 2:
                            results.append({
                                'id': anime_code,
                                'title': title[:100],
                                'url': urljoin(self.base_url, href),
                                'image': '',
                                'released': 'Unknown',
                                'source': 'animeheaven'
                            })
                    except:
                        continue
            
            # METHOD 3: Look for specific patterns in the page
            if not results:
                print("DEBUG: Method 2 failed, trying Method 3...")
                # Look for any text that might be anime titles
                for element in soup.find_all(['div', 'span', 'p', 'h1', 'h2', 'h3', 'h4']):
                    text = element.text.strip()
                    if text and len(text) > 10 and len(text) < 100:
                        # Check if it looks like an anime title
                        if any(keyword in text.lower() for keyword in ['episode', 'season', 'anime', 'watch']):
                            # Try to find a link nearby
                            link = element.find('a')
                            if link and link.get('href') and 'anime.php' in link['href']:
                                href = link['href']
                                if '?' in href:
                                    anime_code = href.split('?')[1]
                                else:
                                    anime_code = href.split('/')[-1]
                                
                                results.append({
                                    'id': anime_code,
                                    'title': text[:100],
                                    'url': urljoin(self.base_url, href),
                                    'image': '',
                                    'released': 'Unknown',
                                    'source': 'animeheaven'
                                })
            
            print(f"DEBUG: Total results found: {len(results)}")
            return results[:10]  # Return max 10 results
            
        except Exception as e:
            print(f"DEBUG: Search error: {e}")
            return []
    
    def get_episodes(self, anime_code: str) -> List[Dict]:
        """Get episodes for an anime"""
        try:
            url = f"{self.base_url}/anime.php?{anime_code}"
            response = self.session.get(url, timeout=30)
            
            if response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            episodes = []
            
            # Look for episode links
            for link in soup.find_all('a', href=True):
                href = link['href']
                text = link.text.strip().lower()
                
                if 'watch.php' in href or ('episode' in text and href):
                    try:
                        # Try to extract episode number
                        ep_num = 1
                        
                        # From text
                        ep_match = re.search(r'episode\s*(\d+)', text, re.IGNORECASE)
                        if ep_match:
                            ep_num = int(ep_match.group(1))
                        else:
                            # From URL
                            url_match = re.search(r'[&?]e=(\d+)', href)
                            if url_match:
                                ep_num = int(url_match.group(1))
                        
                        episodes.append({
                            'number': ep_num,
                            'id': href,
                            'url': urljoin(self.base_url, href),
                            'title': link.text.strip() or f"Episode {ep_num}"
                        })
                    except:
                        continue
            
            # Sort and remove duplicates
            episodes.sort(key=lambda x: x['number'])
            
            # Remove duplicates by episode number
            unique_episodes = []
            seen_numbers = set()
            for ep in episodes:
                if ep['number'] not in seen_numbers:
                    unique_episodes.append(ep)
                    seen_numbers.add(ep['number'])
            
            return unique_episodes
            
        except Exception as e:
            print(f"DEBUG: Get episodes error: {e}")
            return []
    
    def get_download_links(self, episode_path: str) -> List[Dict]:
        """Get download links for an episode"""
        try:
            if not episode_path.startswith('http'):
                url = urljoin(self.base_url, episode_path)
            else:
                url = episode_path
            
            response = self.session.get(url, timeout=30)
            
            if response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            links = []
            
            # Look for video sources
            video = soup.find('video')
            if video:
                # Check source tags
                sources = video.find_all('source')
                for source in sources:
                    src = source.get('src')
                    if src:
                        links.append({
                            'url': src if src.startswith('http') else urljoin(url, src),
                            'quality': source.get('title', 'Unknown'),
                            'type': 'direct'
                        })
            
            # Look for iframes
            iframe = soup.find('iframe')
            if iframe and iframe.get('src'):
                links.append({
                    'url': iframe['src'],
                    'quality': 'HD',
                    'type': 'iframe'
                })
            
            return links
            
        except Exception as e:
            print(f"DEBUG: Get download links error: {e}")
            return []


class MultiSourceScraper:
    """Main scraper class"""
    
    def __init__(self, source: str = 'animeheaven'):
        self.source = source
        self.scraper = AnimeHeavenScraper()
    
    def search(self, query: str) -> List[Dict]:
        return self.scraper.search(query)
    
    def get_episodes(self, anime_id: str) -> List[Dict]:
        return self.scraper.get_episodes(anime_id)
    
    def get_download_links(self, episode_id: str) -> List[Dict]:
        return self.scraper.get_download_links(episode_id)
    
    def set_source(self, source: str):
        # For now, only animeheaven is supported
        pass


class DirectVideoExtractor:
    """Extract direct video links"""
    
    @staticmethod
    def extract_from_url(url: str) -> Optional[str]:
        """Try to extract direct video URL"""
        try:
            # Check if already a video file
            if any(ext in url for ext in ['.mp4', '.m3u8', '.mkv', '.webm']):
                return url
            
            # Otherwise, return the URL as-is
            return url
            
        except:
            return None
