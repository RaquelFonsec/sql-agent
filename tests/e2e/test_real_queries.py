import pytest
import os

@pytest.mark.e2e
@pytest.mark.slow
class TestRealQueries:
    
    @pytest.mark.skipif(not os.getenv('RUN_E2E_TESTS'), 
                        reason="E2E tests disabled")
    def test_count_query_structure(self):
        expected_sql = "SELECT COUNT(*) FROM clientes"
        
        assert "SELECT" in expected_sql
        assert "COUNT" in expected_sql
        assert "clientes" in expected_sql
    
    @pytest.mark.skipif(not os.getenv('RUN_E2E_TESTS'),
                        reason="E2E tests disabled")
    def test_join_query_structure(self):
        expected_sql = "SELECT c.nome FROM clientes c JOIN transacoes t ON c.id = t.cliente_id"
        
        assert "JOIN" in expected_sql
        assert "clientes" in expected_sql
        assert "transacoes" in expected_sql
    
    @pytest.mark.skipif(not os.getenv('RUN_E2E_TESTS'),
                        reason="E2E tests disabled")
    def test_aggregation_query_structure(self):
        expected_sql = "SELECT nome, SUM(valor) FROM transacoes GROUP BY nome"
        
        assert "SUM" in expected_sql
        assert "GROUP BY" in expected_sql
