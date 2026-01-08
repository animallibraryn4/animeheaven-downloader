#!/usr/bin/env python3
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test directly accessing AnimeHeaven
import requests
from bs4 import BeautifulSoup

def test_direct_access():
    print("="*60)
    print("Testing direct access to AnimeHeaven")
    print("="*60)
    
    # Test 1: Direct POST request
    print("\n1. Testing POST request to search.php...")
    
    url = "https://animeheaven.me/search.php"
    data = {'q': 'Naruto', 'search': 'Search'}
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Referer': 'https://animeheaven.me/',
        'Origin': 'https://animeheaven.me'
    }
    
    try:
        response = requests.post(url, data=data, headers=headers, timeout=30)
        print(f"   Status Code: {response.status_code}")
        print(f"   Response Length: {len(response.text)} characters")
        
        # Save response for inspection
        with open('response_dump.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        print("   Response saved to 'response_dump.html'")
        
        # Quick analysis
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Count links
        all_links = soup.find_all('a', href=True)
        anime_links = [link for link in all_links if 'anime.php' in link['href']]
        print(f"   Total links: {len(all_links)}")
        print(f"   Anime links: {len(anime_links)}")
        
        if anime_links:
            print("\n   First 5 anime links found:")
            for i, link in enumerate(anime_links[:5], 1):
                print(f"   {i}. Text: '{link.text.strip()[:50]}'")
                print(f"      Href: {link['href'][:80]}")
        
        # Look for any text containing "Naruto"
        naruto_elements = soup.find_all(text=lambda text: text and 'naruto' in text.lower())
        print(f"\n   Elements containing 'Naruto': {len(naruto_elements)}")
        
        if naruto_elements:
            print("   Sample 'Naruto' texts:")
            for text in naruto_elements[:3]:
                print(f"   - '{text.strip()[:100]}'")
        
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 2: Try GET request to main page
    print("\n2. Testing GET request to main page...")
    
    try:
        main_page = requests.get("https://animeheaven.me/", headers=headers, timeout=30)
        print(f"   Status Code: {main_page.status_code}")
        
        soup = BeautifulSoup(main_page.text, 'html.parser')
        
        # Look for popular anime
        print("   Looking for popular anime sections...")
        
        # Check page structure
        print("\n   Page structure analysis:")
        print(f"   Title tags: {len(soup.find_all('title'))}")
        print(f"   Div tags: {len(soup.find_all('div'))}")
        print(f"   Links with 'anime.php': {len(soup.find_all('a', href=lambda x: x and 'anime.php' in x))}")
        
        # Look for any anime listings
        for div in soup.find_all('div', class_=True):
            classes = div.get('class', [])
            if any(cls in ['video', 'item', 'anime'] for cls in classes):
                print(f"   Found div with classes: {classes}")
                links = div.find_all('a')
                if links:
                    print(f"   Contains {len(links)} links")
        
    except Exception as e:
        print(f"   Error: {e}")

def test_scraper():
    print("\n" + "="*60)
    print("Testing Scraper Class")
    print("="*60)
    
    try:
        from plugins.scraper import MultiSourceScraper
        
        scraper = MultiSourceScraper('animeheaven')
        
        # Test search
        print("\nTesting search for 'Naruto'...")
        results = scraper.search('Naruto')
        
        if results:
            print(f"✅ Found {len(results)} results!")
            print("\nResults:")
            for i, result in enumerate(results, 1):
                print(f"{i}. {result.get('title', 'No title')}")
                print(f"   ID: {result.get('id', 'No ID')}")
                print(f"   URL: {result.get('url', 'No URL')[:80]}...")
                print()
        else:
            print("❌ No results found")
            
            # Try alternative search
            print("\nTrying alternative search terms...")
            for term in ['One Piece', 'Attack on Titan', 'Demon Slayer']:
                print(f"\nSearching for '{term}'...")
                results = scraper.search(term)
                if results:
                    print(f"✅ Found {len(results)} results for '{term}'!")
                    for result in results[:2]:
                        print(f"  - {result.get('title')}")
                    break
                else:
                    print(f"❌ No results for '{term}'")
        
    except Exception as e:
        print(f"❌ Scraper test error: {type(e).__name__}: {e}")

if __name__ == '__main__':
    test_direct_access()
    test_scraper()
    
    print("\n" + "="*60)
    print("TROUBLESHOOTING TIPS:")
    print("="*60)
    print("1. Check if https://animeheaven.me is accessible in your browser")
    print("2. If blocked, use a VPN")
    print("3. Check the 'response_dump.html' file to see what the site returns")
    print("4. The site might have anti-bot measures")
    print("5. Try searching for very popular anime like 'One Piece'")
