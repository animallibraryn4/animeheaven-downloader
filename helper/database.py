import sqlite3
from datetime import datetime
from contextlib import contextmanager
from config import DATABASE_URL


class DatabaseManager:
    def __init__(self):
        self.conn = None
        self.init_db()
    
    @contextmanager
    def get_cursor(self):
        conn = sqlite3.connect('anime_bot.db')
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        finally:
            cursor.close()
            conn.close()
    
    def init_db(self):
        """Initialize database tables"""
        with self.get_cursor() as cursor:
            # Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_downloads INTEGER DEFAULT 0
                )
            ''')
            
            # Downloads table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS downloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    anime_url TEXT,
                    episode INTEGER,
                    file_path TEXT,
                    status TEXT DEFAULT 'pending',
                    download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
    
    def add_user(self, user_id: int, first_name: str, username: str = None):
        """Add or update user"""
        with self.get_cursor() as cursor:
            cursor.execute('''
                INSERT OR REPLACE INTO users (user_id, username, first_name)
                VALUES (?, ?, ?)
            ''', (user_id, username, first_name))
    
    def add_download(self, user_id: int, anime_url: str, episode: int, file_path: str):
        """Record a download"""
        with self.get_cursor() as cursor:
            cursor.execute('''
                INSERT INTO downloads (user_id, anime_url, episode, file_path, status)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, anime_url, episode, file_path, 'completed'))
            
            # Update user's total downloads
            cursor.execute('''
                UPDATE users 
                SET total_downloads = total_downloads + 1 
                WHERE user_id = ?
            ''', (user_id,))
    
    def get_user_stats(self, user_id: int) -> dict:
        """Get user download statistics"""
        with self.get_cursor() as cursor:
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_downloads,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                    MAX(download_date) as last_download
                FROM downloads 
                WHERE user_id = ?
            ''', (user_id,))
            
            row = cursor.fetchone()
            return {
                'total_downloads': row[0] or 0,
                'successful_downloads': row[1] or 0,
                'failed_downloads': row[2] or 0,
                'last_download': row[3]
            }
    
    def get_user_active_downloads(self, user_id: int):
        """Get user's active downloads"""
        with self.get_cursor() as cursor:
            cursor.execute('''
                SELECT * FROM downloads 
                WHERE user_id = ? AND status = 'pending'
            ''', (user_id,))
            return cursor.fetchall()
