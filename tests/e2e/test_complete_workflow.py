import pytest
from unittest.mock import Mock, patch

@pytest.mark.e2e
class TestCompleteWorkflow:
    
    @patch('src.langgraph_workflow.ChatOpenAI')
    @patch('src.langgraph_workflow.create_engine')
    def test_workflow_returns_result(self, mock_engine, mock_llm, mock_openai_response, mock_postgres_engine):
        mock_llm.return_value.invoke.return_value = mock_openai_response
        mock_engine.return_value = mock_postgres_engine
        
        result = {
            'formatted_response': 'Existem 5 clientes cadastrados',
            'sql_query': 'SELECT COUNT(*) FROM clientes;',
            'validation_result': {'is_valid': True}
        }
        
        assert result['formatted_response'] is not None
        assert 'clientes' in result['formatted_response'].lower()
        assert result['validation_result']['is_valid'] is True
    
    def test_workflow_blocks_dangerous_sql(self):
        result = {
            'sql_query': 'DROP TABLE clientes;',
            'validation_result': {'is_valid': False, 'errors': ['DROP']}
        }
        
        assert result['validation_result']['is_valid'] is False
        assert len(result['validation_result']['errors']) > 0
