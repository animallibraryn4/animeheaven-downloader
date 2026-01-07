import time
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from plugins.exceptions import RequestBlocked
from config import ANIMEHEAVEN_ABUSE_MSG, BLOCKED_TIMEOUT


class Scraper:
    """Animeheaven scraper using headless Chrome"""
    
    def __init__(self, anime: str):
        self.__anime = self.__convert_url(anime)
        self.__driver = self.__get_driver()
    
    def get(self, episode: str) -> list:
        """Return list of download links for given episode"""
        url = f'{self.__anime}{episode}'
        
        try:
            self.__driver.get(url)
            
            # Wait for page to load
            wait = WebDriverWait(self.__driver, 10)
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # Check if blocked
            source = self.__driver.page_source
            self.__is_blocked(source)
            
            soup = BeautifulSoup(source, 'html.parser')
            result = soup.find_all('source')
            
            return [download['src'] for download in result] if result else None
            
        except Exception as e:
            print(f"Error scraping episode {episode}: {e}")
            return None
    
    def __get_driver(self):
        """Setup headless Chrome driver"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # For Koyeb/Railway deployment
        chrome_options.binary_location = os.getenv('GOOGLE_CHROME_BIN', '/usr/bin/google-chrome')
        
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=chrome_options)
    
    def __is_blocked(self, html: str) -> bool:
        if html.find(ANIMEHEAVEN_ABUSE_MSG) != -1:
            raise RequestBlocked
        return False
    
    def __convert_url(self, url: str) -> str:
        """Convert anime overall preview url to episode url"""
        url = urlparse(url)
        return f'{url.scheme}://{url.netloc}/watch.php?{url.query}&e='
    
    def close(self):
        """Close the driver"""
        if self.__driver:
            self.__driver.quit()
