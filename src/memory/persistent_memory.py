from typing import Dict, List, Any, Optional
from datetime import datetime
import json
import sqlite3
import logging

logger = logging.getLogger(__name__)


class PersistentMemory:
    def __init__(self, db_path: str = 'memory.db'):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS conversation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    sql_query TEXT,
                    result TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_session 
                ON conversation_history(user_id, session_id)
            ''')
            conn.commit()
    
    def save_interaction(self, user_id: str, session_id: str, 
                        question: str, sql_query: Optional[str] = None,
                        result: Optional[Any] = None, metadata: Optional[Dict] = None):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO conversation_history 
                    (user_id, session_id, question, sql_query, result, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    user_id,
                    session_id,
                    question,
                    sql_query,
                    json.dumps(result) if result else None,
                    json.dumps(metadata) if metadata else None
                ))
                conn.commit()
                logger.info(f"Interaction saved for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to save interaction: {e}")
    
    def get_user_history(self, user_id: str, limit: int = 10) -> List[Dict]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT question, sql_query, result, timestamp
                    FROM conversation_history
                    WHERE user_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', (user_id, limit))
                
                rows = cursor.fetchall()
                return [
                    {
                        'question': row[0],
                        'sql_query': row[1],
                        'result': json.loads(row[2]) if row[2] else None,
                        'timestamp': row[3]
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to retrieve user history: {e}")
            return []
    
    def get_session_context(self, user_id: str, session_id: str) -> List[Dict]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT question, sql_query, result, timestamp
                    FROM conversation_history
                    WHERE user_id = ? AND session_id = ?
                    ORDER BY timestamp ASC
                ''', (user_id, session_id))
                
                rows = cursor.fetchall()
                return [
                    {
                        'question': row[0],
                        'sql_query': row[1],
                        'result': json.loads(row[2]) if row[2] else None,
                        'timestamp': row[3]
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to retrieve session context: {e}")
            return []


memory = PersistentMemory()