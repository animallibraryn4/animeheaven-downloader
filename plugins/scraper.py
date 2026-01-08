import requests
import re
import json
from typing import Dict, List, Optional
from urllib.parse import quote, urlparse, urljoin

from bs4 import BeautifulSoup

from .exceptions import SourceError, NoResultsFound


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
        self.search_url = f"{self.base_url}/search"
    
    def search(self, query: str) -> List[Dict]:
        """Search anime on AnimeHeaven"""
        try:
            # AnimeHeaven search uses GET with 'q' parameter
            params = {'q': query}
            response = self.session.get(self.search_url, params=params, timeout=15)
            response.raise_for_status()
            
            # Check if we got blocked
            if 'abuse protection' in response.text.lower():
                raise SourceError("Site blocked due to abuse protection. Please wait and try again.")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # Find anime items - AnimeHeaven search results are usually in divs
            anime_items = soup.select('div.anime_list_body ul li, div.episode_list div.name, a[href*="/info/"]')
            
            if not anime_items:
                # Try alternative selectors
                anime_items = soup.select('.video')
            
            for item in anime_items:
                try:
                    # Find link element
                    link = item.select_one('a')
                    if not link or not link.get('href'):
                        continue
                    
                    href = link['href']
                    
                    # Skip if it's not an anime info page
                    if '/info/' not in href:
                        continue
                    
                    # Extract anime ID from URL (e.g., /info/naruto -> naruto)
                    anime_id = href.split('/info/')[1].strip('/')
                    
                    # Get title
                    title = link.get('title', '') or link.text.strip()
                    
                    # Find image if available
                    img = item.select_one('img')
                    image_url = img['src'] if img and img.get('src') else ""
                    
                    # Find description/summary
                    description = ""
                    desc_elem = item.select_one('.description, .summary, p')
                    if desc_elem:
                        description = desc_elem.text.strip()[:100]
                    
                    results.append({
                        'id': anime_id,
                        'title': title,
                        'url': urljoin(self.base_url, href),
                        'image': image_url,
                        'description': description,
                        'released': 'Unknown',  # AnimeHeaven doesn't show release year in search
                        'source': 'animeheaven'
                    })
                    
                except Exception as e:
                    print(f"Error parsing AnimeHeaven result: {e}")
                    continue
            
            # If no results found with above method, try another approach
            if not results:
                # Look for all links with /info/
                all_links = soup.find_all('a', href=lambda x: x and '/info/' in x)
                for link in all_links[:20]:  # Limit to first 20
                    try:
                        href = link['href']
                        anime_id = href.split('/info/')[1].strip('/')
                        title = link.get('title', '') or link.text.strip()
                        
                        if title and len(title) > 2:  # Filter out very short titles
                            results.append({
                                'id': anime_id,
                                'title': title,
                                'url': urljoin(self.base_url, href),
                                'image': '',
                                'description': '',
                                'released': 'Unknown',
                                'source': 'animeheaven'
                            })
                    except:
                        continue
            
            return results[:15]  # Return max 15 results
            
        except Exception as e:
            print(f"AnimeHeaven search error: {e}")
            raise SourceError(f"Search failed: {str(e)[:100]}")
    
    def get_episodes(self, anime_id: str) -> List[Dict]:
        """Get all episodes for an anime"""
        try:
            url = f"{self.base_url}/info/{anime_id}"
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            episodes = []
            
            # Find episode links - AnimeHeaven episode links usually have pattern like /watch/naruto-episode-1
            episode_links = soup.find_all('a', href=lambda x: x and f'/{anime_id}-episode-' in x)
            
            for link in episode_links:
                try:
                    href = link['href']
                    
                    # Extract episode number from URL
                    ep_match = re.search(r'episode-(\d+)', href)
                    if not ep_match:
                        continue
                    
                    ep_num = int(ep_match.group(1))
                    
                    # Get episode title from link text
                    ep_title = link.text.strip()
                    if not ep_title:
                        ep_title = f"Episode {ep_num}"
                    
                    episodes.append({
                        'number': ep_num,
                        'id': href.strip('/'),
                        'url': urljoin(self.base_url, href),
                        'title': ep_title
                    })
                    
                except Exception as e:
                    print(f"Error parsing episode: {e}")
                    continue
            
            # If no episodes found with above pattern, try alternative
            if not episodes:
                # Look for episode list in the page
                episode_section = soup.select_one('#episode_list, .episode_list, .list_episode')
                if episode_section:
                    episode_items = episode_section.find_all('a')
                    for idx, link in enumerate(episode_items):
                        try:
                            href = link.get('href', '')
                            if href and 'episode' in href.lower():
                                # Try to extract episode number from URL or text
                                ep_num_match = re.search(r'(\d+)', link.text)
                                if ep_num_match:
                                    ep_num = int(ep_num_match.group(1))
                                else:
                                    ep_num = idx + 1
                                
                                episodes.append({
                                    'number': ep_num,
                                    'id': href.strip('/'),
                                    'url': urljoin(self.base_url, href),
                                    'title': link.text.strip() or f"Episode {ep_num}"
                                })
                        except:
                            continue
            
            # Sort by episode number
            episodes.sort(key=lambda x: x['number'])
            return episodes
            
        except Exception as e:
            print(f"Error getting episodes: {e}")
            raise SourceError(f"Failed to get episodes: {str(e)}")
    
    def get_download_links(self, episode_id: str) -> List[Dict]:
        """Get download/video links for an episode"""
        try:
            # Construct episode URL
            if episode_id.startswith('http'):
                url = episode_id
            else:
                url = f"{self.base_url}/{episode_id}"
            
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            download_links = []
            
            # AnimeHeaven usually embeds videos from various sources
            # Look for iframes first
            iframes = soup.select('iframe')
            for iframe in iframes:
                src = iframe.get('src')
                if src:
                    # Check if it's a video embed
                    if any(x in src for x in ['stream', 'vid', 'embed', 'video', 'player']):
                        download_links.append({
                            'url': src if src.startswith('http') else urljoin(self.base_url, src),
                            'quality': 'HD',
                            'type': 'iframe',
                            'source': 'animeheaven'
                        })
            
            # Look for video tags
            video_tags = soup.select('video')
            for video in video_tags:
                # Check source tags inside video
                sources = video.select('source')
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
                
                # Check if video has src attribute directly
                video_src = video.get('src')
                if video_src:
                    download_links.append({
                        'url': video_src if video_src.startswith('http') else urljoin(url, video_src),
                        'quality': 'HD',
                        'type': 'direct',
                        'source': 'animeheaven'
                    })
            
            # Look for download buttons/links
            download_divs = soup.select('.download_div, .dowload, .download_links')
            for div in download_divs:
                links = div.find_all('a')
                for link in links:
                    href = link.get('href', '')
                    text = link.text.strip().lower()
                    
                    if href and any(x in href.lower() for x in ['.mp4', '.m3u8', '.mkv', 'download']):
                        quality = 'Unknown'
                        if '1080' in text or 'full hd' in text:
                            quality = '1080p'
                        elif '720' in text:
                            quality = '720p'
                        elif '480' in text or 'sd' in text:
                            quality = '480p'
                        elif '360' in text:
                            quality = '360p'
                        
                        download_links.append({
                            'url': href if href.startswith('http') else urljoin(self.base_url, href),
                            'quality': quality,
                            'type': 'direct',
                            'source': 'animeheaven'
                        })
            
            # Extract from JavaScript variables (common in streaming sites)
            script_text = str(soup.find_all('script'))
            
            # Look for video URLs in JavaScript
            video_patterns = [
                r'file:\s*["\'](.*?\.(?:mp4|m3u8|mkv))["\']',
                r'src:\s*["\'](.*?\.(?:mp4|m3u8|mkv))["\']',
                r'"(https?://[^"]+\.(?:mp4|m3u8|mkv)[^"]*)"',
                r'video_url\s*[:=]\s*["\'](.*?)["\']',
                r'file_link\s*[:=]\s*["\'](.*?)["\']'
            ]
            
            for pattern in video_patterns:
                matches = re.findall(pattern, script_text, re.IGNORECASE)
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0]
                    
                    if match and not match.startswith('blob:'):
                        download_links.append({
                            'url': match if match.startswith('http') else urljoin(self.base_url, match),
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
            
            return unique_links[:5]  # Return only first 5 unique links
            
        except Exception as e:
            print(f"Error getting AnimeHeaven download links: {e}")
            # Return at least the episode page URL as a fallback
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
                # Return empty list instead of error
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
            # Return empty list instead of raising error
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
            # For AnimeHeaven
            if 'animeheaven' in url:
                return DirectVideoExtractor.extract_animeheaven(url)
            
            # For other common streaming sites
            elif any(x in url for x in ['streamtape', 'mp4upload', 'dood', 'mixdrop']):
                # These sites need special handling
                return url
            
            # For direct video links
            elif any(ext in url for ext in ['.mp4', '.m3u8', '.mkv']):
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
            
            # Look for direct video links
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
                r'"(https?://[^"]+\.(?:mp4|m3u8|mkv)[^"]*)"',
                r'video_url\s*[:=]\s*["\'](.*?)["\']'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, script_text, re.DOTALL | re.IGNORECASE)
                if match:
                    video_url = match.group(1)
                    if any(ext in video_url for ext in ['.mp4', '.m3u8', '.mkv']):
                        return video_url
            
        except Exception as e:
            print(f"AnimeHeaven extraction error: {e}")
        
        return None
