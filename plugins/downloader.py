import time
import os
import urllib.request
from tqdm import tqdm


class Downloader:
    def __init__(self, directory: str):
        self.__directory = self.__exists(directory)
        self.__downloads = {}
        self.__current_download = None
    
    def download(self, name: str, url: str):
        """Download file with progress bar"""
        path = f'{self.get_path()}/{name}'
        self.__current_download = name
        
        try:
            # Create directory if not exists
            os.makedirs(os.path.dirname(path), exist_ok=True)
            
            # Download with progress bar
            with tqdm(unit='B', unit_scale=True, miniters=1, desc=name) as t:
                urllib.request.urlretrieve(
                    url, 
                    path, 
                    reporthook=self.__progress_hook(t)
                )
            
            if os.path.exists(path):
                self.__downloads[name] = path
                return True
            return False
            
        except Exception as e:
            print(f"Download error: {e}")
            return False
    
    def get_path(self) -> str:
        return self.__directory
    
    def get_downloads(self) -> dict:
        return self.__downloads
    
    def __exists(self, directory: str) -> str:
        """Check if directory exists, else create one"""
        if not os.path.isdir(directory):
            os.makedirs(directory)
        return os.path.abspath(directory)
    
    def __progress_hook(self, t):
        """Download progress hook for tqdm"""
        def update_to(b=1, bsize=1, tsize=None):
            if tsize is not None:
                t.total = tsize
            t.update(b * bsize - t.n)
        return update_to
    
    def cleanup(self):
        """Clean up downloaded files"""
        for file_path in self.__downloads.values():
            if os.path.exists(file_path):
                os.remove(file_path)
        self.__downloads.clear()
