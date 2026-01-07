from urllib.parse import urlparse


def is_valid_anime(anime: str) -> bool:
    """Check if URL is a valid AnimeHeaven URL"""
    try:
        url = urlparse(anime)
        if not all([url.scheme, url.netloc]):
            return False
        
        # Check if it's animeheaven domain
        if 'animeheaven' not in url.netloc:
            return False
            
        return True
    except:
        return False


def get_episodes(ep: str) -> list:
    """Parse episode range string into list of episodes"""
    try:
        episodes = []
        
        # Handle comma-separated episodes
        if ',' in ep:
            parts = ep.split(',')
            for part in parts:
                if '-' in part:
                    start, end = map(int, part.split('-'))
                    episodes.extend(range(start, end + 1))
                else:
                    episodes.append(int(part))
        # Handle range
        elif '-' in ep:
            start, end = map(int, ep.split('-'))
            episodes = list(range(start, end + 1))
        # Single episode
        else:
            episodes = [int(ep)]
        
        # Remove duplicates and sort
        episodes = sorted(set(episodes))
        return episodes if episodes else []
        
    except ValueError:
        return []
