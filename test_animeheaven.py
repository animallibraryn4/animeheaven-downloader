#!/usr/bin/env python3
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    # Try to import from plugins folder
    from plugins.scraper import MultiSourceScraper
    print("✅ Successfully imported from plugins folder")
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Trying direct import...")
    
    # Try creating a simple scraper directly
    import requests
    from bs4 import BeautifulSoup
    
    class SimpleScraper:
        def search(self, query):
            print(f"Searching for: {query}")
            
            # Try to search AnimeHeaven
            url = "https://animeheaven.me/search.php"
            data = {'q': query, 'search': 'Search'}
            
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                
                response = requests.post(url, data=data, headers=headers, timeout=10)
                print(f"Response status: {response.status_code}")
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Look for anime links
                    anime_links = soup.find_all('a', href=lambda x: x and 'anime.php' in x)
                    
                    results = []
                    for link in anime_links[:5]:  # First 5 results
                        title = link.get('title', '') or link.text.strip()
                        href = link['href']
                        
                        if title and href:
                            # Extract anime code
                            if '?' in href:
                                anime_code = href.split('?')[1]
                            else:
                                anime_code = href
                            
                            results.append({
                                'id': anime_code,
                                'title': title,
                                'url': f"https://animeheaven.me/{href}" if not href.startswith('http') else href,
                                'source': 'animeheaven'
                            })
                    
                    print(f"Found {len(results)} results")
                    return results
                else:
                    print(f"Failed to get search page. Status: {response.status_code}")
                    
            except Exception as e:
                print(f"Error during search: {e}")
            
            return []
    
    scraper = SimpleScraper()
    results = scraper.search("Naruto")
    
    if results:
        print("\nSearch Results:")
        for i, result in enumerate(results, 1):
            print(f"{i}. {result['title']}")
            print(f"   ID: {result['id']}")
    else:
        print("No results found or website is blocked")

# Test the scraper
print("\n" + "="*50)
print("Testing AnimeHeaven Search")
print("="*50)

try:
    # Create scraper instance
    scraper = MultiSourceScraper('animeheaven')
    
    # Test search
    print("Searching for 'Naruto'...")
    results = scraper.search('Naruto')
    
    if results:
        print(f"✅ Found {len(results)} results!")
        print("\nFirst 3 results:")
        for i, result in enumerate(results[:3], 1):
            print(f"{i}. {result.get('title', 'No title')}")
            print(f"   ID: {result.get('id', 'No ID')}")
    else:
        print("❌ No results found")
        
except Exception as e:
    print(f"❌ Error: {type(e).__name__}: {e}")
