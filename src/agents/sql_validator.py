import sqlparse
from sqlparse.sql import IdentifierList, Identifier, Where
from sqlparse.tokens import Keyword, DML
from src.orchestration.mcp_context import MCPContext
from src.observability.tracer import tracer
import logging
import re

logger = logging.getLogger(__name__)


class SQLValidator:
    ALLOWED_OPERATIONS = {'SELECT'}
    DANGEROUS_PATTERNS = [
        r'DROP\s+TABLE',
        r'DELETE\s+FROM',
        r'TRUNCATE',
        r'ALTER\s+TABLE',
        r'CREATE\s+TABLE',
        r'INSERT\s+INTO',
        r'UPDATE\s+',
        r'EXEC',
        r'EXECUTE',
        r';.*SELECT',  # Multiple statements
        r'--',  # SQL comments
        r'/\*',  # Block comments
    ]
    
    ALLOWED_TABLES = {'clientes', 'produtos', 'transacoes'}
    
    def validate(self, context: MCPContext) -> MCPContext:
        with tracer.start_span("sql_validator"):
            try:
                sql = context.generated_sql
                if not sql:
                    raise ValueError("No SQL query to validate")
                
                logger.info(f"Validating SQL: {sql}")
                
                validation_result = {
                    'is_valid': True,
                    'errors': [],
                    'warnings': [],
                    'optimizations': []
                }
                
                validation_result = self._check_dangerous_patterns(sql, validation_result)
                validation_result = self._check_allowed_operations(sql, validation_result)
                validation_result = self._check_table_references(sql, validation_result)
                validation_result = self._check_syntax(sql, validation_result)
                validation_result = self._suggest_optimizations(sql, validation_result)
                
                if validation_result['errors']:
                    validation_result['is_valid'] = False
                
                context.validation_result = validation_result
                
                tracer.log_interaction("sql_validator", {
                    "sql": sql,
                    "validation_result": validation_result
                })
                
                if not validation_result['is_valid']:
                    error_msg = "; ".join(validation_result['errors'])
                    context.add_error("sql_validator", error_msg)
                    logger.warning(f"SQL validation failed: {error_msg}")
                else:
                    logger.info("SQL validation passed")
                
            except Exception as e:
                error_msg = f"SQL validation error: {str(e)}"
                logger.error(error_msg)
                context.add_error("sql_validator", error_msg)
                context.validation_result = {'is_valid': False, 'errors': [error_msg]}
                tracer.log_error("sql_validator", e)
        
        return context
    
    def _check_dangerous_patterns(self, sql: str, result: dict) -> dict:
        sql_upper = sql.upper()
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, sql_upper, re.IGNORECASE):
                result['errors'].append(f"Dangerous pattern detected: {pattern}")
        return result
    
    def _check_allowed_operations(self, sql: str, result: dict) -> dict:
        parsed = sqlparse.parse(sql)
        if not parsed:
            result['errors'].append("Failed to parse SQL")
            return result
        
        for statement in parsed:
            first_token = statement.token_first(skip_ws=True, skip_cm=True)
            if first_token and first_token.ttype is DML:
                operation = first_token.value.upper()
                if operation not in self.ALLOWED_OPERATIONS:
                    result['errors'].append(f"Operation not allowed: {operation}")
        
        return result
    
    def _check_table_references(self, sql: str, result: dict) -> dict:
        sql_lower = sql.lower()
        for table in self.ALLOWED_TABLES:
            if table in sql_lower:
                continue
        
        tokens = sql_lower.split()
        for i, token in enumerate(tokens):
            if token in ('from', 'join'):
                if i + 1 < len(tokens):
                    table_name = tokens[i + 1].strip('();,')
                    if table_name not in self.ALLOWED_TABLES and not table_name.startswith(tuple(self.ALLOWED_TABLES)):
                        result['warnings'].append(f"Unknown table reference: {table_name}")
        
        return result
    
    def _check_syntax(self, sql: str, result: dict) -> dict:
        try:
            parsed = sqlparse.parse(sql)
            if not parsed or len(parsed) == 0:
                result['errors'].append("Invalid SQL syntax")
            
            if sql.count('(') != sql.count(')'):
                result['errors'].append("Unbalanced parentheses")
            
        except Exception as e:
            result['errors'].append(f"Syntax error: {str(e)}")
        
        return result
    
    def _suggest_optimizations(self, sql: str, result: dict) -> dict:
        sql_upper = sql.upper()
        
        if 'SELECT *' in sql_upper:
            result['optimizations'].append("Consider specifying column names instead of SELECT *")
        
        if 'LIMIT' not in sql_upper and 'COUNT' not in sql_upper:
            result['optimizations'].append("Consider adding LIMIT clause to prevent large result sets")
        
        if re.search(r'WHERE.*OR.*OR', sql_upper):
            result['optimizations'].append("Multiple OR conditions might benefit from IN clause")
        
        return result


sql_validator = SQLValidator()