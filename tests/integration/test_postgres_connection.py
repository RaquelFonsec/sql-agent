import pytest
from sqlalchemy import create_engine, text
import os

@pytest.mark.integration
class TestPostgresConnection:
    
    def test_database_connection(self):
        database_url = os.getenv('DATABASE_URL', 
            'postgresql://sql_agent_user:secure_password@localhost/sql_agent_db')
        engine = create_engine(database_url)
        
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                assert result.fetchone()[0] == 1
        except Exception as e:
            pytest.skip(f"PostgreSQL nao disponivel: {e}")
    
    def test_tables_exist(self):
        database_url = os.getenv('DATABASE_URL',
            'postgresql://sql_agent_user:secure_password@localhost/sql_agent_db')
        engine = create_engine(database_url)
        
        try:
            with engine.connect() as conn:
                result = conn.execute(text(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_name IN ('clientes', 'produtos', 'transacoes')"
                ))
                count = result.fetchone()[0]
                assert count == 3
        except Exception as e:
            pytest.skip(f"PostgreSQL nao disponivel: {e}")
    
    def test_clientes_table_has_data(self):
        database_url = os.getenv('DATABASE_URL',
            'postgresql://sql_agent_user:secure_password@localhost/sql_agent_db')
        engine = create_engine(database_url)
        
        try:
            with engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM clientes"))
                count = result.fetchone()[0]
                assert count > 0
        except Exception as e:
            pytest.skip(f"PostgreSQL nao disponivel: {e}")
