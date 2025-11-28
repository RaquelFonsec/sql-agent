from sqlalchemy import text
from src.config.database import get_db_session
from src.orchestration.mcp_context import MCPContext
from src.observability.tracer import tracer
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


def convert_decimals(obj):
    """Converte Decimal para float recursivamente"""
    if isinstance(obj, list):
        return [convert_decimals(item) for item in obj]
    elif isinstance(obj, dict):
        return {key: convert_decimals(value) for key, value in obj.items()}
    elif isinstance(obj, Decimal):
        return float(obj)
    else:
        return obj


class SmartQueryExecutor:
    """AGENTE 4 EVOLUIDO: Executor com streaming e paginacao"""
    
    MAX_ROWS_IN_MEMORY = 1000
    BATCH_SIZE = 100
    QUERY_TIMEOUT = 30
    
    def execute(self, context: MCPContext) -> MCPContext:
        with tracer.start_span("smart_query_executor"):
            try:
                if not context.validation_result or not context.validation_result.get('is_valid'):
                    context.execution_result = {
                        'success': False,
                        'error': 'Query validation failed',
                        'data': []
                    }
                    return context
                
                sql = context.generated_sql
                logger.info(f"Executing SQL with smart limits: {sql[:100]}...")
                
                result = self._execute_with_streaming(sql, context)
                context.execution_result = result
                
                tracer.log_interaction("smart_query_executor", {
                    "sql": sql,
                    "rows_returned": len(result.get('data', [])),
                    "truncated": result.get('truncated', False),
                    "execution_time": result.get('execution_time', 0)
                })
                
                logger.info(f"Query executed: {len(result.get('data', []))} rows")
                
            except Exception as e:
                error_msg = f"Query execution failed: {str(e)}"
                logger.error(error_msg)
                context.add_error("query_executor", error_msg)
                context.execution_result = {
                    'success': False,
                    'error': error_msg,
                    'data': []
                }
                tracer.log_error("query_executor", e)
        
        return context
    
    def _execute_with_streaming(self, sql: str, context: MCPContext) -> dict:
        """Executa query com streaming (batches)"""
        import time
        start_time = time.time()
        
        try:
            with get_db_session() as session:
                session.execute(text(f"SET statement_timeout = '{self.QUERY_TIMEOUT}s'"))
                
                result_proxy = session.execute(text(sql))
                columns = list(result_proxy.keys())
                
                all_rows = []
                truncated = False
                
                while len(all_rows) < self.MAX_ROWS_IN_MEMORY:
                    batch = result_proxy.fetchmany(self.BATCH_SIZE)
                    
                    if not batch:
                        break
                    
                    all_rows.extend(batch)
                    
                    if len(all_rows) >= self.MAX_ROWS_IN_MEMORY:
                        truncated = True
                        all_rows = all_rows[:self.MAX_ROWS_IN_MEMORY]
                        break
                
                # Converte para dicionarios
                data = [dict(zip(columns, row)) for row in all_rows]
                
                # Converte Decimals para float
                data = convert_decimals(data)
                
                execution_time = time.time() - start_time
                
                if truncated:
                    logger.warning(f"Results truncated to {self.MAX_ROWS_IN_MEMORY} rows")
                
                return {
                    'success': True,
                    'data': data,
                    'columns': columns,
                    'row_count': len(data),
                    'truncated': truncated,
                    'execution_time': round(execution_time, 3)
                }
                
        except Exception as e:
            logger.error(f"Streaming execution failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'data': []
            }


query_executor = SmartQueryExecutor()
