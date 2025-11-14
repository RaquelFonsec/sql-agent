from sqlalchemy import text
from src.config.database import get_db_session
from src.orchestration.mcp_context import MCPContext
from src.observability.tracer import tracer
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class QueryExecutor:
    def __init__(self):
        self.max_results = 1000
    
    def execute(self, context: MCPContext) -> MCPContext:
        with tracer.start_span("query_executor"):
            try:
                if not context.validation_result or not context.validation_result.get('is_valid'):
                    error_msg = "Cannot execute invalid SQL query"
                    logger.error(error_msg)
                    context.add_error("query_executor", error_msg)
                    return context
                
                sql = context.generated_sql
                logger.info(f"Executing SQL: {sql}")
                
                with get_db_session() as session:
                    result = session.execute(text(sql))
                    
                    if result.returns_rows:
                        rows = result.fetchall()
                        columns = result.keys()
                        
                        data = [
                            dict(zip(columns, row))
                            for row in rows[:self.max_results]
                        ]
                        
                        execution_result = {
                            'success': True,
                            'data': data,
                            'row_count': len(data),
                            'truncated': len(rows) > self.max_results
                        }
                    else:
                        execution_result = {
                            'success': True,
                            'message': 'Query executed successfully',
                            'rows_affected': result.rowcount
                        }
                    
                    context.execution_result = execution_result
                    
                    tracer.log_interaction("query_executor", {
                        "sql": sql,
                        "row_count": execution_result.get('row_count', 0),
                        "success": True
                    })
                    
                    logger.info(f"Query executed successfully, returned {execution_result.get('row_count', 0)} rows")
                
            except Exception as e:
                error_msg = f"Query execution failed: {str(e)}"
                logger.error(error_msg)
                context.add_error("query_executor", error_msg)
                context.execution_result = {
                    'success': False,
                    'error': str(e)
                }
                tracer.log_error("query_executor", e)
        
        return context


query_executor = QueryExecutor()