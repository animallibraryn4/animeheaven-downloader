import os
import requests
from tqdm import tqdm


class Downloader:
    def __init__(self, directory: str):
        self.__directory = self.__ensure_directory(directory)
        self.__downloads = {}
    
    def download(self, name: str, url: str) -> bool:
        """Download file with progress bar"""
        path = os.path.join(self.__directory, name)
        
        try:
            # Create directory if not exists
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            response = requests.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            
            with open(path, 'wb') as file, tqdm(
                desc=name,
                total=total_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
            ) as bar:
                for data in response.iter_content(chunk_size=1024):
                    size = file.write(data)
                    bar.update(size)
            
            if os.path.exists(path):
                self.__downloads[name] = path
                print(f"✓ Downloaded: {name}")
                return True
            
            return False
            
        except Exception as e:
            print(f"✗ Download error for {name}: {e}")
            return False
    
    def get_path(self) -> str:
        return self.__directory
    
    def get_downloads(self) -> dict:
        return self.__downloads
    
    def __ensure_directory(self, directory: str) -> str:
        """Ensure directory exists"""
        if not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)
        return os.path.abspath(directory)
    
    def cleanup(self):
        """Clean up downloaded files"""
        for file_path in self.__downloads.values():
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass
        self.__downloads.clear()
