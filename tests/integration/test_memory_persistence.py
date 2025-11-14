import pytest
import sqlite3
import os
from datetime import datetime

class SimplePersistentMemory:
    def __init__(self, db_path="test_memory.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                question TEXT NOT NULL,
                sql_query TEXT,
                result TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()
    
    def save_interaction(self, user_id, session_id, question, sql_query, result):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO conversation_history (user_id, session_id, question, sql_query, result)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, session_id, question, sql_query, result))
        conn.commit()
        conn.close()
    
    def get_user_history(self, user_id, limit=10):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM conversation_history 
            WHERE user_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        """, (user_id, limit))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    
    def cleanup(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

@pytest.mark.integration
class TestMemoryPersistence:
    
    def test_save_interaction(self):
        memory = SimplePersistentMemory("test_save.db")
        
        memory.save_interaction(
            user_id="test_user",
            session_id="test_session",
            question="Teste?",
            sql_query="SELECT 1;",
            result="1"
        )
        
        history = memory.get_user_history("test_user")
        
        assert len(history) == 1
        assert history[0]['question'] == "Teste?"
        
        memory.cleanup()
    
    def test_get_user_history(self):
        memory = SimplePersistentMemory("test_history.db")
        
        for i in range(5):
            memory.save_interaction(
                user_id="test_user",
                session_id="session",
                question=f"Pergunta {i}",
                sql_query=f"SELECT {i};",
                result=str(i)
            )
        
        history = memory.get_user_history("test_user", limit=3)
        
        assert len(history) == 3
        
        memory.cleanup()
    
    def test_session_isolation(self):
        memory = SimplePersistentMemory("test_isolation.db")
        
        memory.save_interaction(
            user_id="user1",
            session_id="session1",
            question="User 1",
            sql_query="SELECT 1;",
            result="1"
        )
        
        memory.save_interaction(
            user_id="user2",
            session_id="session2",
            question="User 2",
            sql_query="SELECT 2;",
            result="2"
        )
        
        user1_history = memory.get_user_history("user1")
        user2_history = memory.get_user_history("user2")
        
        assert len(user1_history) == 1
        assert len(user2_history) == 1
        assert user1_history[0]['question'] == "User 1"
        assert user2_history[0]['question'] == "User 2"
        
        memory.cleanup()
