import json
import os
from datetime import datetime
import sqlite3
from typing import List, Dict, Optional

class DatabaseManager:
    def __init__(self, db_path='database/downloads.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create downloads table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                anime_title TEXT NOT NULL,
                episodes TEXT NOT NULL,
                download_path TEXT NOT NULL,
                download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_size TEXT,
                status TEXT DEFAULT 'completed'
            )
        ''')
        
        # Create users table for statistics
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_downloads INTEGER DEFAULT 0
            )
        ''')
        
        # Create search_history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                query TEXT NOT NULL,
                search_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                results_count INTEGER DEFAULT 0
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_download(self, user_id: int, anime_title: str, episodes: str, download_path: str):
        """Save download record to database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Insert download record
            cursor.execute('''
                INSERT INTO downloads (user_id, anime_title, episodes, download_path)
                VALUES (?, ?, ?, ?)
            ''', (user_id, anime_title, episodes, download_path))
            
            # Update user statistics
            cursor.execute('''
                INSERT OR IGNORE INTO users (user_id, total_downloads)
                VALUES (?, 0)
            ''', (user_id,))
            
            cursor.execute('''
                UPDATE users SET total_downloads = total_downloads + 1
                WHERE user_id = ?
            ''', (user_id,))
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            print(f"Database error: {e}")
            return False
    
    def get_user_downloads(self, user_id: int, limit: int = 10) -> List[Dict]:
        """Get download history for a user."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM downloads 
                WHERE user_id = ? 
                ORDER BY download_date DESC 
                LIMIT ?
            ''', (user_id, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            # Convert rows to dictionaries
            downloads = []
            for row in rows:
                downloads.append(dict(row))
            
            return downloads
            
        except Exception as e:
            print(f"Database error: {e}")
            return []
    
    def save_search(self, user_id: int, query: str, results_count: int = 0):
        """Save search query to history."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO search_history (user_id, query, results_count)
                VALUES (?, ?, ?)
            ''', (user_id, query, results_count))
            
            conn.commit()
            conn.close()
            
            return True
            
        except Exception as e:
            print(f"Database error: {e}")
            return False
    
    def get_user_stats(self, user_id: int) -> Dict:
        """Get user statistics."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get user info
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            user_row = cursor.fetchone()
            
            # Get download count
            cursor.execute('SELECT COUNT(*) as count FROM downloads WHERE user_id = ?', (user_id,))
            download_count = cursor.fetchone()['count']
            
            # Get recent searches
            cursor.execute('''
                SELECT query, search_date FROM search_history 
                WHERE user_id = ? 
                ORDER BY search_date DESC 
                LIMIT 5
            ''', (user_id,))
            
            recent_searches = []
            for row in cursor.fetchall():
                recent_searches.append({
                    'query': row['query'],
                    'date': row['search_date']
                })
            
            conn.close()
            
            stats = {
                'user_id': user_id,
                'total_downloads': download_count,
                'recent_searches': recent_searches,
                'join_date': user_row['join_date'] if user_row else None
            }
            
            return stats
            
        except Exception as e:
            print(f"Database error: {e}")
            return {}
    
    def cleanup_old_records(self, days: int = 30):
        """Clean up records older than specified days."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Clean old downloads
            cursor.execute('''
                DELETE FROM downloads 
                WHERE julianday('now') - julianday(download_date) > ?
            ''', (days,))
            
            # Clean old search history
            cursor.execute('''
                DELETE FROM search_history 
                WHERE julianday('now') - julianday(search_date) > ?
            ''', (days,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            return deleted_count
            
        except Exception as e:
            print(f"Database cleanup error: {e}")
            return 0
