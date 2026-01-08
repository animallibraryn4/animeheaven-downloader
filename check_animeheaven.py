#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup
import json

def check_website():
    print("Checking AnimeHeaven website...")
    
    # Test the main page
    url = "https://animeheaven.me"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        print(f"1. Testing main page: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Length: {len(response.text)} characters")
        
        # Save a sample
        with open('animeheaven_sample.html', 'w', encoding='utf-8') as f:
            f.write(response.text[:5000])
        print("   Sample saved to animeheaven_sample.html")
        
        # Look for search form
        soup = BeautifulSoup(response.text, 'html.parser')
        forms = soup.find_all('form')
        print(f"   Forms found: {len(forms)}")
        
        for form in forms:
            if form.find('input', {'name': 'q'}):
                print(f"   Found search form! Action: {form.get('action', 'N/A')}")
        
        # Look for anime links
        anime_links = soup.find_all('a', href=lambda x: x and 'anime' in x.lower())
        print(f"   Anime-related links: {len(anime_links)}")
        
        # Show first 5 links
        print("\n   First 5 anime links:")
        for link in anime_links[:5]:
            print(f"   - Text: '{link.text.strip()[:50]}'")
            print(f"     Href: {link.get('href', 'N/A')[:80]}")
        
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test search directly
    print("\n2. Testing search function...")
    try:
        search_url = "https://animeheaven.me/search.php"
        data = {'q': 'Naruto', 'search': 'Search'}
        
        response = requests.post(search_url, data=data, headers=headers, timeout=10)
        print(f"   Search response status: {response.status_code}")
        print(f"   Search response length: {len(response.text)} characters")
        
        # Save search results
        with open('search_results.html', 'w', encoding='utf-8') as f:
            f.write(response.text)
        print("   Search results saved to search_results.html")
        
        # Analyze search results
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Count various elements
        print("\n   Search page analysis:")
        print(f"   Total links: {len(soup.find_all('a'))}")
        print(f"   Div elements: {len(soup.find_all('div'))}")
        
        # Look for any anime listings
        for div in soup.find_all('div', class_=True):
            classes = ' '.join(div.get('class', []))
            if 'anime' in classes.lower() or 'video' in classes.lower():
                print(f"   Found div with classes: {classes}")
                # Check for links in this div
                links = div.find_all('a')
                if links:
                    print(f"   Contains {len(links)} links")
                    for link in links[:2]:
                        print(f"     Link: {link.get('href', 'N/A')[:60]}")
        
    except Exception as e:
        print(f"   Search error: {e}")

if __name__ == '__main__':
    check_website()
    print("\n" + "="*60)
    print("IMPORTANT: If the website returns 403 or 'abuse protection',")
    print("you need to use a VPN or proxy!")
    print("="*60)
