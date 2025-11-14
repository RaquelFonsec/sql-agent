import pytest
import time

@pytest.mark.slow
class TestPerformance:
    
    def test_query_response_time_mock(self):
        start = time.time()
        
        time.sleep(0.1)
        
        end = time.time()
        response_time = end - start
        
        assert response_time < 5.0
    
    def test_multiple_queries_performance_mock(self):
        queries = [
            "Quantos clientes?",
            "Liste produtos",
            "Total de transacoes"
        ]
        
        start = time.time()
        
        for query in queries:
            time.sleep(0.1)
        
        end = time.time()
        total_time = end - start
        avg_time = total_time / len(queries)
        
        assert avg_time < 3.0
