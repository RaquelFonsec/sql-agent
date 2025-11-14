import pytest
from unittest.mock import Mock, MagicMock

# ---------------------------
# Banco de Dados Fake
# ---------------------------

@pytest.fixture
def test_database_url():
    return "postgresql://sql_agent_user:secure_password@localhost/sql_agent_test_db"

# ---------------------------
# Mock do LLM (OpenAI / LangChain)
# ---------------------------

@pytest.fixture
def mock_openai_response():
    mock = Mock()
    mock.content = "SELECT COUNT(*) FROM clientes;"
    return mock

@pytest.fixture
def mock_llm(mock_openai_response):
    mock = Mock()
    mock.invoke.return_value = mock_openai_response
    return mock

# ---------------------------
# Schema usado pelo SQL Generator
# ---------------------------

@pytest.fixture
def sample_schema():
    return """
    Tabelas:
    - clientes (id, nome, email, saldo)
    - produtos (id, nome, preco)
    - transacoes (id, cliente_id, produto_id, valor)
    """

# ---------------------------
# Mock Engine PostgreSQL — 
# ---------------------------

@pytest.fixture
def mock_postgres_engine():
    
    mock_engine = MagicMock()

    # conexão simulada
    mock_connection = MagicMock()

    # cursor simulado
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [(1,)]

    # execute() retorna cursor
    mock_connection.execute.return_value = mock_cursor

    # connect() retorna objeto com context manager funcionando
    mock_engine.connect.return_value.__enter__.return_value = mock_connection
    mock_engine.connect.return_value.__exit__.return_value = None

    return mock_engine
