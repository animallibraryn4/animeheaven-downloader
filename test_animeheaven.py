#!/usr/bin/env python3
import sys
sys.path.append('.')

from scraper import MultiSourceScraper

def test_search():
    print("Testing AnimeHeaven search...")
    scraper = MultiSourceScraper('animeheaven')
    
    try:
        # Test search
        print("Searching for 'Naruto'...")
        results = scraper.search('Naruto')
        
        if results:
            print(f"✅ Found {len(results)} results!")
            print("\nFirst 5 results:")
            for i, result in enumerate(results[:5], 1):
                print(f"{i}. {result['title']}")
                print(f"   ID: {result['id']}")
                print(f"   URL: {result['url']}")
                print()
            
            # Test getting episodes for first result
            if results:
                anime_id = results[0]['id']
                print(f"\nTesting episodes for '{results[0]['title']}' (ID: {anime_id})...")
                episodes = scraper.get_episodes(anime_id)
                
                if episodes:
                    print(f"✅ Found {len(episodes)} episodes!")
                    print("\nFirst 5 episodes:")
                    for ep in episodes[:5]:
                        print(f"  Episode {ep['number']}: {ep['title']}")
                        print(f"    URL: {ep['url']}")
                else:
                    print("❌ No episodes found")
        else:
            print("❌ No results found. The site might be blocked or the search method needs updating.")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    scraper.close()

if __name__ == '__main__':
    test_search()
