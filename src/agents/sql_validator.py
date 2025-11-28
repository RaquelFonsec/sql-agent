import sqlparse
from sqlparse.sql import IdentifierList, Identifier, Where
from sqlparse.tokens import Keyword, DML
from src.orchestration.mcp_context import MCPContext
from src.observability.tracer import tracer
import logging
import re

logger = logging.getLogger(__name__)


class SQLValidatorOptimizer:
    """AGENTE 3 EVOLUÍDO: Validação + Otimização + Estimativa de Custo"""
    
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
        r';.*SELECT',
        r'--',
        r'/\*',
    ]
    
    ALLOWED_TABLES = {'clientes', 'produtos', 'transacoes'}
    
    # 🆕 Limites por tabela (em produção, use valores reais)
    TABLE_SIZES = {
        'clientes': 5,        # Em produção: 3_000_000
        'transacoes': 10,     # Em produção: 150_000_000
        'produtos': 6         # Em produção: 25_000
    }
    
    MAX_RESULT_SIZE = 10000  # Máximo de linhas permitidas
    
    def validate(self, context: MCPContext) -> MCPContext:
        with tracer.start_span("sql_validator_optimizer"):
            try:
                sql = context.generated_sql
                if not sql:
                    raise ValueError("No SQL query to validate")
                
                logger.info(f"Validating and optimizing SQL: {sql}")
                
                validation_result = {
                    'is_valid': True,
                    'errors': [],
                    'warnings': [],
                    'optimizations': [],
                    'estimated_cost': 'low',  # 🆕
                    'estimated_rows': 0,       # 🆕
                    'optimized_sql': sql       # 🆕
                }
                
                # Validações originais
                validation_result = self._check_dangerous_patterns(sql, validation_result)
                validation_result = self._check_allowed_operations(sql, validation_result)
                validation_result = self._check_table_references(sql, validation_result)
                validation_result = self._check_syntax(sql, validation_result)
                
                # 🆕 NOVAS VALIDAÇÕES
                validation_result = self._estimate_query_cost(sql, validation_result, context)
                validation_result = self._check_missing_indexes(sql, validation_result)
                validation_result = self._auto_optimize_query(sql, validation_result)
                validation_result = self._suggest_optimizations(sql, validation_result)
                
                if validation_result['errors']:
                    validation_result['is_valid'] = False
                
                context.validation_result = validation_result
                
                # Se foi otimizada, atualiza a SQL
                if validation_result['optimized_sql'] != sql:
                    logger.info(f"Query optimized: {validation_result['optimized_sql']}")
                    context.generated_sql = validation_result['optimized_sql']
                
                tracer.log_interaction("sql_validator_optimizer", {
                    "sql": sql,
                    "validation_result": validation_result
                })
                
                if not validation_result['is_valid']:
                    error_msg = "; ".join(validation_result['errors'])
                    context.add_error("sql_validator", error_msg)
                    logger.warning(f"SQL validation failed: {error_msg}")
                else:
                    logger.info(f"SQL validated (cost: {validation_result['estimated_cost']})")
                
            except Exception as e:
                error_msg = f"SQL validation error: {str(e)}"
                logger.error(error_msg)
                context.add_error("sql_validator", error_msg)
                context.validation_result = {'is_valid': False, 'errors': [error_msg]}
                tracer.log_error("sql_validator", e)
        
        return context
    
    def _estimate_query_cost(self, sql: str, result: dict, context: MCPContext) -> dict:
        """🆕 Estima custo e número de linhas da query"""
        sql_upper = sql.upper()
        estimated_rows = 0
        cost = "low"
        
        # Identifica tabelas envolvidas
        tables_in_query = []
        for table in self.ALLOWED_TABLES:
            if table.upper() in sql_upper:
                tables_in_query.append(table)
        
        # Estima rows baseado nas tabelas e se tem LIMIT
        if "LIMIT" in sql_upper:
            # Extrai valor do LIMIT
            match = re.search(r'LIMIT\s+(\d+)', sql_upper)
            if match:
                estimated_rows = int(match.group(1))
                cost = "low"
        else:
            # Sem LIMIT, estima pelo pior caso
            if "transacoes" in tables_in_query:
                estimated_rows = self.TABLE_SIZES['transacoes']
                cost = "very_high" if estimated_rows > 1000 else "high"
            elif tables_in_query:
                estimated_rows = max([self.TABLE_SIZES.get(t, 0) for t in tables_in_query])
                cost = "medium" if estimated_rows > 100 else "low"
        
        # Ajusta custo se tiver JOINs
        join_count = sql_upper.count("JOIN")
        if join_count >= 2:
            cost = "high" if cost == "medium" else cost
        
        result['estimated_rows'] = estimated_rows
        result['estimated_cost'] = cost
        
        # ⚠️ Se custo muito alto, adiciona warning
        if cost in ["high", "very_high"]:
            result['warnings'].append(
                f"Query pode retornar {estimated_rows} linhas. "
                f"Considere adicionar LIMIT ou filtros WHERE."
            )
        
        return result
    
    def _check_missing_indexes(self, sql: str, result: dict) -> dict:
        """🆕 Verifica se a query usa colunas sem índice"""
        sql_upper = sql.upper()
        
        # Colunas indexadas conhecidas
        indexed_columns = {
            'clientes': ['id', 'email'],
            'produtos': ['id', 'categoria'],
            'transacoes': ['id', 'cliente_id', 'produto_id', 'data_transacao']
        }
        
        # Verifica WHERE clauses
        if "WHERE" in sql_upper:
            # Extrai colunas do WHERE (simplificado)
            where_part = sql_upper.split("WHERE")[1].split("GROUP")[0].split("ORDER")[0]
            
            # Procura por colunas não indexadas em tabelas grandes
            if "TRANSACOES" in sql_upper and "TRANSACOES.DATA_TRANSACAO" not in where_part:
                result['warnings'].append(
                    "Query em 'transacoes' sem filtro por data_transacao (coluna indexada). "
                    "Performance pode ser lenta."
                )
        
        return result
    
    def _auto_optimize_query(self, sql: str, result: dict) -> dict:
        """🆕 Otimiza automaticamente a query"""
        optimized = sql
        sql_upper = sql.upper()
        
        # 1. Adiciona LIMIT se não tiver e for tabela grande
        if "LIMIT" not in sql_upper:
            tables_in_query = [t for t in self.ALLOWED_TABLES if t.upper() in sql_upper]
            
            if "transacoes" in tables_in_query:
                # Tabela gigante - força LIMIT
                optimized = optimized.rstrip(';') + " LIMIT 100;"
                result['optimizations'].append("✅ LIMIT 100 adicionado automaticamente (tabela grande)")
            
            elif len(tables_in_query) >= 2:
                # Múltiplas tabelas (JOINs) - adiciona LIMIT moderado
                optimized = optimized.rstrip(';') + " LIMIT 1000;"
                result['optimizations'].append("✅ LIMIT 1000 adicionado (query com JOINs)")
        
        # 2. Substitui SELECT * por colunas específicas (se possível detectar contexto)
        if "SELECT *" in sql_upper and "COUNT" not in sql_upper:
            result['warnings'].append(
                "SELECT * detectado. Considere especificar apenas colunas necessárias."
            )
        
        result['optimized_sql'] = optimized
        return result
    
    # Métodos originais mantidos...
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
        
        if re.search(r'WHERE.*OR.*OR', sql_upper):
            result['optimizations'].append("Multiple OR conditions might benefit from IN clause")
        
        return result


sql_validator = SQLValidatorOptimizer()