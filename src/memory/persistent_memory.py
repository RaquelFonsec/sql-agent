from typing import Dict, List, Any, Optional
from datetime import datetime
import json
import sqlite3
import logging
import hashlib

logger = logging.getLogger(__name__)


class SemanticMemoryCache:
    """MEMÓRIA EVOLUÍDA: Cache semântico + histórico"""
    
    def __init__(self, db_path: str = 'memory.db'):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Tabela original
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
            
            # 🆕 Nova tabela: cache semântico
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS semantic_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_hash TEXT UNIQUE NOT NULL,
                    question TEXT NOT NULL,
                    sql_query TEXT NOT NULL,
                    result TEXT NOT NULL,
                    hit_count INTEGER DEFAULT 1,
                    last_used DATETIME DEFAULT CURRENT_TIMESTAMP,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Índices
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_session 
                ON conversation_history(user_id, session_id)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_question_hash
                ON semantic_cache(question_hash)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_last_used
                ON semantic_cache(last_used DESC)
            ''')
            
            conn.commit()
    
    def _normalize_question(self, question: str) -> str:
        """Normaliza pergunta para cache (case-insensitive, sem pontuação extra)"""
        import re
        normalized = question.lower().strip()
        normalized = re.sub(r'[?!.,;:]', '', normalized)
        normalized = re.sub(r'\s+', ' ', normalized)
        return normalized
    
    def _hash_question(self, question: str) -> str:
        """Gera hash da pergunta normalizada"""
        normalized = self._normalize_question(question)
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def check_cache(self, question: str) -> Optional[dict]:
        """🆕 Verifica se pergunta está no cache"""
        question_hash = self._hash_question(question)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT sql_query, result, hit_count
                    FROM semantic_cache
                    WHERE question_hash = ?
                ''', (question_hash,))
                
                row = cursor.fetchone()
                
                if row:
                    # Atualiza hit_count e last_used
                    cursor.execute('''
                        UPDATE semantic_cache
                        SET hit_count = hit_count + 1,
                            last_used = CURRENT_TIMESTAMP
                        WHERE question_hash = ?
                    ''', (question_hash,))
                    conn.commit()
                    
                    logger.info(f"✅ CACHE HIT! (hits: {row[2] + 1})")
                    
                    return {
                        'sql_query': row[0],
                        'result': json.loads(row[1]) if row[1] else None,
                        'from_cache': True
                    }
                
                logger.info("❌ Cache miss")
                return None
                
        except Exception as e:
            logger.error(f"Cache check failed: {e}")
            return None
    
    def save_to_cache(self, question: str, sql_query: str, result: Any):
        """🆕 Salva no cache semântico"""
        question_hash = self._hash_question(question)
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Insert or update
                cursor.execute('''
                    INSERT INTO semantic_cache (question_hash, question, sql_query, result)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(question_hash) DO UPDATE SET
                        sql_query = excluded.sql_query,
                        result = excluded.result,
                        last_used = CURRENT_TIMESTAMP
                ''', (
                    question_hash,
                    question,
                    sql_query,
                    json.dumps(result)
                ))
                conn.commit()
                logger.info("Saved to semantic cache")
        except Exception as e:
            logger.error(f"Failed to save to cache: {e}")
    
    def save_interaction(self, user_id: str, session_id: str, 
                        question: str, sql_query: Optional[str] = None,
                        result: Optional[Any] = None, metadata: Optional[Dict] = None):
        """Salva no histórico (método original mantido)"""
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
                
                # 🆕 Também salva no cache se tiver resultado válido
                if sql_query and result:
                    self.save_to_cache(question, sql_query, result)
                
                logger.info(f"Interaction saved for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to save interaction: {e}")
    
    def get_cache_statistics(self) -> Dict:
        """🆕 Estatísticas do cache"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('SELECT COUNT(*), SUM(hit_count) FROM semantic_cache')
                row = cursor.fetchone()
                
                return {
                    'total_cached_queries': row[0] or 0,
                    'total_cache_hits': row[1] or 0,
                    'cache_hit_rate': f"{(row[1] / max(row[0], 1) * 100):.1f}%"
                }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {}
    
    # Métodos originais mantidos...
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


memory = SemanticMemoryCache()