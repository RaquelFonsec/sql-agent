import pytest

class MockMCPContext:
    def __init__(self, user_id, session_id, original_question):
        self.user_id = user_id
        self.session_id = session_id
        self.original_question = original_question
        self.generated_sql = None

class TestMCPContext:
    
    def test_context_initialization(self):
        context = MockMCPContext(
            user_id="test_user",
            session_id="test_session",
            original_question="Teste"
        )
        
        assert context.user_id == "test_user"
        assert context.session_id == "test_session"
        assert context.original_question == "Teste"
    
    def test_context_update(self):
        context = MockMCPContext(
            user_id="test_user",
            session_id="test_session",
            original_question="Teste"
        )
        
        context.generated_sql = "SELECT * FROM clientes;"
        
        assert context.generated_sql is not None
        assert "SELECT" in context.generated_sql
