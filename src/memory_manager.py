import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional


class MemoryManager:
    """Gerencia histórico de consultas e conversas"""
    
    def __init__(self, db_path='memory.db'):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Tabela de histórico
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS query_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    question TEXT NOT NULL,
                    sql_query TEXT,
                    result TEXT,
                    execution_time FLOAT,
                    success BOOLEAN,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Índices
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_session 
                ON query_history(user_id, session_id)
            ''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON query_history(timestamp DESC)
            ''')
            
            conn.commit()
    
    def save_query(self, user_id: str, session_id: str, question: str, 
                   sql_query: Optional[str] = None, result: Optional[str] = None,
                   execution_time: float = 0.0, success: bool = True):
        """Salvar consulta no histórico"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO query_history 
                (user_id, session_id, question, sql_query, result, execution_time, success)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, session_id, question, sql_query, result, execution_time, success))
            conn.commit()
    
    def get_user_history(self, user_id: str, limit: int = 10) -> List[Dict]:
        """Recuperar histórico do usuário"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT question, sql_query, result, timestamp, success
                FROM query_history
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (user_id, limit))
            
            rows = cursor.fetchall()
            return [
                {
                    'question': row[0],
                    'sql_query': row[1],
                    'result': row[2],
                    'timestamp': row[3],
                    'success': row[4]
                }
                for row in rows
            ]
    
    def get_session_context(self, session_id: str) -> List[Dict]:
        """Recuperar contexto da sessão atual"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT question, sql_query, result
                FROM query_history
                WHERE session_id = ?
                ORDER BY timestamp ASC
            ''', (session_id,))
            
            rows = cursor.fetchall()
            return [
                {
                    'question': row[0],
                    'sql_query': row[1],
                    'result': row[2]
                }
                for row in rows
            ]
    
    def get_statistics(self, user_id: str) -> Dict:
        """Estatísticas do usuário"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Total de consultas
            cursor.execute('''
                SELECT COUNT(*), 
                       SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
                       AVG(execution_time) as avg_time
                FROM query_history
                WHERE user_id = ?
            ''', (user_id,))
            
            row = cursor.fetchone()
            
            return {
                'total_queries': row[0],
                'successful_queries': row[1],
                'average_time': round(row[2], 3) if row[2] else 0
            }


# Teste
if __name__ == "__main__":
    memory = MemoryManager()
    
    # Salvar algumas consultas de exemplo
    memory.save_query(
        user_id="user123",
        session_id="session1",
        question="Quantos clientes temos?",
        sql_query="SELECT COUNT(*) FROM clientes",
        result="5",
        execution_time=0.05,
        success=True
    )
    
    # Ver histórico
    history = memory.get_user_history("user123")
    print("Histórico:", history)
    
    # Estatísticas
    stats = memory.get_statistics("user123")
    print("Estatísticas:", stats)
