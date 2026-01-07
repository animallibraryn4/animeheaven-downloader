import os
import requests
import subprocess
from tqdm import tqdm
from typing import Optional


class SmartDownloader:
    """Smart downloader with multiple methods"""
    
    def __init__(self, directory: str = 'downloads'):
        self.directory = self._ensure_directory(directory)
        self.downloads = {}
    
    def download(self, url: str, filename: str, method: str = 'requests') -> Optional[str]:
        """Download file using specified method"""
        
        # Clean filename
        filename = self._clean_filename(filename)
        filepath = os.path.join(self.directory, filename)
        
        try:
            if method == 'requests':
                success = self._download_requests(url, filepath)
            elif method == 'wget':
                success = self._download_wget(url, filepath)
            elif method == 'curl':
                success = self._download_curl(url, filepath)
            else:
                success = self._download_requests(url, filepath)
            
            if success and os.path.exists(filepath):
                self.downloads[filename] = filepath
                return filepath
            
        except Exception as e:
            print(f"Download failed: {e}")
        
        return None
    
    def _download_requests(self, url: str, filepath: str) -> bool:
        """Download using requests library with progress bar"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://gogoanime3.co/'
            }
            
            response = requests.get(url, stream=True, headers=headers, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            
            with open(filepath, 'wb') as file, tqdm(
                desc=os.path.basename(filepath),
                total=total_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
            ) as bar:
                for data in response.iter_content(chunk_size=8192):
                    size = file.write(data)
                    bar.update(size)
            
            return True
            
        except Exception as e:
            print(f"Requests download error: {e}")
            return False
    
    def _download_wget(self, url: str, filepath: str) -> bool:
        """Download using wget command"""
        try:
            cmd = ['wget', '-O', filepath, url]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
    
    def _download_curl(self, url: str, filepath: str) -> bool:
        """Download using curl command"""
        try:
            cmd = ['curl', '-L', '-o', filepath, url]
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0
        except:
            return False
    
    def download_m3u8(self, m3u8_url: str, filename: str) -> Optional[str]:
        """Download HLS/m3u8 streams using ffmpeg"""
        filepath = os.path.join(self.directory, filename)
        
        try:
            # Check if ffmpeg is available
            if not self._check_ffmpeg():
                print("FFmpeg not found. Cannot download m3u8 streams.")
                return None
            
            cmd = [
                'ffmpeg', '-i', m3u8_url,
                '-c', 'copy',
                '-bsf:a', 'aac_adtstoasc',
                filepath,
                '-y'  # Overwrite output file
            ]
            
            print(f"Downloading HLS stream: {filename}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0 and os.path.exists(filepath):
                self.downloads[filename] = filepath
                return filepath
            
        except Exception as e:
            print(f"HLS download error: {e}")
        
        return None
    
    def _check_ffmpeg(self) -> bool:
        """Check if ffmpeg is installed"""
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True)
            return True
        except:
            return False
    
    def _ensure_directory(self, directory: str) -> str:
        """Ensure download directory exists"""
        if not os.path.isdir(directory):
            os.makedirs(directory, exist_ok=True)
        return os.path.abspath(directory)
    
    def _clean_filename(self, filename: str) -> str:
        """Clean filename to remove invalid characters"""
        # Remove invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Ensure .mp4 extension
        if not filename.lower().endswith('.mp4'):
            filename += '.mp4'
        
        return filename
    
    def get_downloads(self) -> dict:
        return self.downloads
    
    def cleanup(self):
        """Remove all downloaded files"""
        for filepath in self.downloads.values():
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                except:
                    pass
        self.downloads.clear()
