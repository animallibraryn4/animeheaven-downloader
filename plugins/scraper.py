
import requests
import re
import json
from typing import Dict, List, Optional
from urllib.parse import quote, urlparse, urljoin, parse_qs

from bs4 import BeautifulSoup

# Import from same directory
try:
    from .exceptions import SourceError, NoResultsFound
except ImportError:
    # Define locally if import fails
    class SourceError(Exception):
        pass
    
    class NoResultsFound(Exception):
        pass

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
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://animeheaven.me/'
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


class AnimeHeavenScraper(BaseScraper):
    """Scraper for AnimeHeaven.me"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://animeheaven.me"
        self.search_url = f"{self.base_url}/search.php"
    
    def search(self, query: str) -> List[Dict]:
        """Search anime on AnimeHeaven"""
        try:
            # AnimeHeaven uses POST request for search
            data = {
                'q': query,
                'search': 'Search'
            }
            
            response = self.session.post(self.search_url, data=data, timeout=15)
            response.raise_for_status()
            
            # Check for abuse protection
            if 'abuse protection' in response.text.lower():
                raise SourceError("Site blocked due to abuse protection. Please wait and try again.")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # Look for anime listings - AnimeHeaven shows results in a specific pattern
            # Check for anime grid items
            anime_items = soup.select('div.anime_grid_item, div.video, div.item, .anime-item')
            
            if not anime_items:
                # Try alternative selectors
                anime_items = soup.select('a[href*="anime.php"]')
                
                if not anime_items:
                    # Look for any links that might be anime
                    all_links = soup.find_all('a', href=True)
                    anime_items = [link for link in all_links if 'anime.php' in link['href']]
            
            for item in anime_items[:20]:  # Limit to 20 results
                try:
                    # Get the link
                    if hasattr(item, 'get'):
                        link = item
                    else:
                        link = item.find('a')
                    
                    if not link or not link.get('href'):
                        continue
                    
                    href = link['href']
                    
                    # Only process anime.php links
                    if 'anime.php' not in href:
                        continue
                    
                    # Extract anime code from URL (e.g., anime.php?nc7bk -> nc7bk)
                    if '?' in href:
                        anime_code = href.split('?')[1]
                    else:
                        continue
                    
                    # Get title
                    title = ""
                    
                    # Try to find title in different ways
                    if link.get('title'):
                        title = link['title']
                    elif link.text.strip():
                        title = link.text.strip()
                    else:
                        # Look for title in parent elements
                        parent = link.parent
                        if parent and parent.text.strip():
                            title = parent.text.strip()
                    
                    # Clean up title
                    title = title.replace('\n', ' ').replace('\t', ' ').strip()
                    title = ' '.join(title.split())  # Remove extra spaces
                    
                    if not title or len(title) < 2:
                        continue
                    
                    # Get image if available
                    image_url = ""
                    img = link.find('img') if hasattr(link, 'find') else None
                    if not img and hasattr(item, 'find'):
                        img = item.find('img')
                    
                    if img and img.get('src'):
                        image_url = img['src']
                        if not image_url.startswith('http'):
                            image_url = urljoin(self.base_url, image_url)
                    
                    results.append({
                        'id': anime_code,  # Use the anime code as ID
                        'title': title[:100],  # Limit title length
                        'url': urljoin(self.base_url, href),
                        'image': image_url,
                        'released': 'Unknown',
                        'source': 'animeheaven'
                    })
                    
                except Exception as e:
                    print(f"Error parsing AnimeHeaven result: {e}")
                    continue
            
            # If still no results, try a different approach
            if not results:
                # Look for all divs that might contain anime info
                divs = soup.select('div')
                for div in divs:
                    # Check if div contains anime.php link
                    anime_link = div.find('a', href=lambda x: x and 'anime.php' in x)
                    if anime_link:
                        try:
                            href = anime_link['href']
                            anime_code = href.split('?')[1] if '?' in href else ''
                            
                            title = anime_link.get('title', '') or anime_link.text.strip()
                            if title:
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
            
            # Remove duplicates by URL
            unique_results = []
            seen_urls = set()
            for result in results:
                if result['url'] not in seen_urls:
                    unique_results.append(result)
                    seen_urls.add(result['url'])
            
            return unique_results[:15]  # Return max 15 unique results
            
        except Exception as e:
            print(f"AnimeHeaven search error: {e}")
            # Try to return empty list instead of error for now
            return []
    
    def get_episodes(self, anime_code: str) -> List[Dict]:
        """Get all episodes for an anime"""
        try:
            url = f"{self.base_url}/anime.php?{anime_code}"
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            episodes = []
            
            # Look for episode links - they usually have pattern like watch.php?...
            # First, try to find the episode list container
            episode_container = soup.select_one('#episode_list, .episode_list, .list_episode, .episodes')
            
            if episode_container:
                episode_links = episode_container.find_all('a', href=True)
            else:
                # If no container found, look for all watch.php links
                episode_links = soup.find_all('a', href=lambda x: x and 'watch.php' in x)
            
            for link in episode_links:
                try:
                    href = link['href']
                    
                    # Extract episode info from URL or text
                    episode_num = 1
                    
                    # Try to get episode number from URL parameters
                    if '?' in href:
                        params = href.split('?')[1]
                        # Look for e= parameter or similar
                        if 'e=' in params:
                            ep_match = re.search(r'e=(\d+)', params)
                            if ep_match:
                                episode_num = int(ep_match.group(1))
                    
                    # If not found in URL, try to extract from link text
                    if episode_num == 1:
                        text = link.text.strip()
                        ep_match = re.search(r'Episode\s*(\d+)', text, re.IGNORECASE)
                        if ep_match:
                            episode_num = int(ep_match.group(1))
                        else:
                            # Look for any number in the text
                            num_match = re.search(r'(\d+)', text)
                            if num_match:
                                episode_num = int(num_match.group(1))
                    
                    # Get episode title
                    ep_title = link.text.strip()
                    if not ep_title:
                        ep_title = f"Episode {episode_num}"
                    
                    # Create episode ID
                    ep_id = href
                    
                    episodes.append({
                        'number': episode_num,
                        'id': ep_id,
                        'url': urljoin(self.base_url, href),
                        'title': ep_title[:50]
                    })
                    
                except Exception as e:
                    print(f"Error parsing episode link: {e}")
                    continue
            
            # If no episodes found with watch.php, try alternative
            if not episodes:
                # Look for any links that might be episodes
                all_links = soup.find_all('a', href=True)
                for link in all_links:
                    href = link['href']
                    text = link.text.strip().lower()
                    
                    if any(x in text for x in ['episode', 'ep', 'watch', 'view']) and not href.startswith('#'):
                        try:
                            # Try to extract episode number
                            ep_match = re.search(r'(\d+)', text)
                            ep_num = int(ep_match.group(1)) if ep_match else len(episodes) + 1
                            
                            episodes.append({
                                'number': ep_num,
                                'id': href,
                                'url': urljoin(self.base_url, href),
                                'title': link.text.strip()[:50]
                            })
                        except:
                            continue
            
            # Sort by episode number and remove duplicates
            episodes.sort(key=lambda x: x['number'])
            
            # Remove duplicates by URL
            unique_episodes = []
            seen_urls = set()
            for ep in episodes:
                if ep['url'] not in seen_urls:
                    unique_episodes.append(ep)
                    seen_urls.add(ep['url'])
            
            return unique_episodes
            
        except Exception as e:
            print(f"Error getting episodes: {e}")
            raise SourceError(f"Failed to get episodes: {str(e)}")
    
    def get_download_links(self, episode_path: str) -> List[Dict]:
        """Get download/video links for an episode"""
        try:
            # Construct full URL
            if episode_path.startswith('http'):
                url = episode_path
            elif episode_path.startswith('/'):
                url = f"{self.base_url}{episode_path}"
            else:
                url = f"{self.base_url}/{episode_path}"
            
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            download_links = []
            
            # First, look for the video player
            video_player = soup.select_one('#video_player, .video_player, video, iframe')
            
            if video_player:
                # Check if it's an iframe
                if video_player.name == 'iframe':
                    iframe_src = video_player.get('src')
                    if iframe_src:
                        download_links.append({
                            'url': iframe_src if iframe_src.startswith('http') else urljoin(url, iframe_src),
                            'quality': 'HD',
                            'type': 'iframe',
                            'source': 'animeheaven'
                        })
                
                # Check if it's a video tag
                elif video_player.name == 'video':
                    # Check for source tags
                    sources = video_player.find_all('source')
                    for source in sources:
                        src = source.get('src')
                        if src:
                            quality = source.get('title', '') or source.get('data-quality', 'Unknown')
                            download_links.append({
                                'url': src if src.startswith('http') else urljoin(url, src),
                                'quality': quality,
                                'type': 'direct',
                                'source': 'animeheaven'
                            })
                    
                    # Check video src attribute
                    video_src = video_player.get('src')
                    if video_src:
                        download_links.append({
                            'url': video_src if video_src.startswith('http') else urljoin(url, video_src),
                            'quality': 'HD',
                            'type': 'direct',
                            'source': 'animeheaven'
                        })
            
            # Look for download buttons
            download_sections = soup.select('.download_div, .dowload, .download_link, a[href*="download"]')
            for section in download_sections:
                # Find all links in download section
                links = section.find_all('a', href=True) if hasattr(section, 'find_all') else []
                if not links and hasattr(section, 'get'):
                    # It might be the link itself
                    links = [section]
                
                for link in links:
                    href = link.get('href', '')
                    text = link.text.strip().lower()
                    
                    if href and any(x in href.lower() for x in ['.mp4', '.m3u8', '.mkv', 'stream', 'video']):
                        quality = 'Unknown'
                        if '1080' in text or 'full hd' in text:
                            quality = '1080p'
                        elif '720' in text:
                            quality = '720p'
                        elif '480' in text or 'sd' in text:
                            quality = '480p'
                        elif '360' in text:
                            quality = '360p'
                        
                        full_url = href if href.startswith('http') else urljoin(url, href)
                        download_links.append({
                            'url': full_url,
                            'quality': quality,
                            'type': 'direct',
                            'source': 'animeheaven'
                        })
            
            # Extract from JavaScript
            script_text = str(soup.find_all('script'))
            
            # Look for various video URL patterns in JavaScript
            patterns = [
                r'(?:file|src|video_url|source)\s*[:=]\s*["\'](https?://[^"\']+\.(?:mp4|m3u8|mkv|webm)[^"\']*)["\']',
                r'(?:file|src|video_url|source)\s*[:=]\s*["\']([^"\']+\.(?:mp4|m3u8|mkv|webm))["\']',
                r'"((?:https?:)?//[^"]+\.(?:mp4|m3u8|mkv|webm)[^"]*)"',
                r'"(/[^"]+\.(?:mp4|m3u8|mkv|webm)[^"]*)"'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, script_text, re.IGNORECASE)
                for match in matches:
                    if match:
                        video_url = match
                        if not video_url.startswith('http'):
                            if video_url.startswith('//'):
                                video_url = 'https:' + video_url
                            else:
                                video_url = urljoin(url, video_url)
                        
                        # Skip blob URLs
                        if not video_url.startswith('blob:'):
                            download_links.append({
                                'url': video_url,
                                'quality': 'HD',
                                'type': 'direct',
                                'source': 'animeheaven'
                            })
            
            # Remove duplicates
            unique_links = []
            seen_urls = set()
            for link in download_links:
                if link['url'] not in seen_urls:
                    unique_links.append(link)
                    seen_urls.add(link['url'])
            
            return unique_links[:10]  # Return max 10 links
            
        except Exception as e:
            print(f"Error getting download links: {e}")
            # Return the episode page itself as a fallback
            return [{
                'url': url,
                'quality': 'Unknown',
                'type': 'page',
                'source': 'animeheaven'
            }]


class AnimePaheScraper(BaseScraper):
    """Scraper for AnimePahe"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://animepahe.com"
    
    def search(self, query: str) -> List[Dict]:
        try:
            search_url = f"{self.base_url}/api"
            params = {
                'm': 'search',
                'q': query,
                'l': 10
            }
            
            response = self.session.get(search_url, params=params, timeout=15)
            
            if response.status_code == 403:
                return []
            
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            if data.get('data'):
                for item in data['data']:
                    results.append({
                        'id': str(item.get('id', '')),
                        'title': item.get('title', 'Unknown'),
                        'url': f"{self.base_url}/anime/{item.get('session', '')}",
                        'released': str(item.get('year', 'N/A')),
                        'image': item.get('poster', ''),
                        'source': 'animepahe'
                    })
            
            return results
            
        except Exception as e:
            print(f"AnimePahe search error: {e}")
            return []


class MultiSourceScraper:
    """Main scraper that supports multiple sources"""
    
    def __init__(self, source: str = 'animeheaven'):
        self.source = source
        self.scrapers = {
            'animeheaven': AnimeHeavenScraper(),
            'animepahe': AnimePaheScraper()
        }
        self.current_scraper = self.scrapers.get(source)
        if not self.current_scraper:
            self.current_scraper = self.scrapers['animeheaven']
    
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


class DirectVideoExtractor:
    """Extract direct video links from various streaming sites"""
    
    @staticmethod
    def extract_from_url(url: str) -> Optional[str]:
        """Try to extract direct video URL from various sources"""
        try:
            # For AnimeHeaven pages
            if 'animeheaven.me' in url:
                return DirectVideoExtractor.extract_animeheaven(url)
            
            # For direct video links
            elif any(ext in url for ext in ['.mp4', '.m3u8', '.mkv', '.webm']):
                return url
                
        except Exception as e:
            print(f"Extraction failed: {e}")
        
        return None
    
    @staticmethod
    def extract_animeheaven(url: str) -> Optional[str]:
        """Extract video from AnimeHeaven page"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://animeheaven.me/'
            }
            
            response = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for video sources
            video = soup.find('video')
            if video:
                # Check source tags
                source = video.find('source')
                if source and source.get('src'):
                    return source['src']
                
                # Check video src
                if video.get('src'):
                    return video['src']
            
            # Check JavaScript for video URLs
            script_text = str(soup.find_all('script'))
            patterns = [
                r'sources:\s*\[.*?file:\s*["\'](.*?)["\']',
                r'file:\s*["\'](.*?)["\']',
                r'src:\s*["\'](.*?)["\']',
                r'video_url\s*[:=]\s*["\'](.*?)["\']'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, script_text, re.DOTALL | re.IGNORECASE)
                if match:
                    video_url = match.group(1)
                    if any(ext in video_url for ext in ['.mp4', '.m3u8', '.mkv', '.webm']):
                        return video_url
            
        except Exception as e:
            print(f"AnimeHeaven extraction error: {e}")
        
        return None
