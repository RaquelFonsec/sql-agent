from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from src.config.settings import settings
from src.orchestration.mcp_context import MCPContext
from src.observability.tracer import tracer
import logging
import re

logger = logging.getLogger(__name__)


class SQLGenerator:
    """AGENTE 2: Gerador de SQL com schema enforcement"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4",
            temperature=0,
            openai_api_key=settings.openai_api_key
        )
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """Voce e um especialista em PostgreSQL que gera queries SQL PRECISAS.

REGRAS CRITICAS - LEIA COM ATENCAO:

1. NOMES DE COLUNAS EXATOS (copie exatamente como esta aqui):
   
   Tabela: clientes
   - id (INTEGER)
   - nome (VARCHAR)
   - email (VARCHAR)
   - created_at (TIMESTAMP)
   
   Tabela: produtos
   - id (INTEGER)
   - nome (VARCHAR)
   - preco (DECIMAL)
   - categoria (VARCHAR)
   
   Tabela: transacoes
   - id (INTEGER)
   - cliente_id (INTEGER)
   - produto_id (INTEGER)
   - quantidade (INTEGER)
   - valor_total (DECIMAL) ATENCAO: E "valor_total", NAO "valor"!
   - data_transacao (TIMESTAMP)

2. NUNCA invente nomes de colunas!
3. Se precisar somar valores de transacoes, use: SUM(transacoes.valor_total)
4. SEMPRE adicione LIMIT 100 (exceto para COUNT)
5. Use aliases claros (AS total_gasto, AS nome_cliente, etc)
6. Use apenas SELECT para leitura de dados
7. Use JOINs apropriados quando necessario
8. Use INNER JOIN a menos que especificado diferente
9. Use parametrizacao para prevenir SQL Injection

EXEMPLOS CORRETOS:
```sql
-- Total gasto por cliente:
SELECT c.nome, SUM(t.valor_total) AS total_gasto
FROM clientes c
JOIN transacoes t ON c.id = t.cliente_id
GROUP BY c.id, c.nome
LIMIT 100;

-- Clientes que compraram X:
SELECT DISTINCT c.nome
FROM clientes c
JOIN transacoes t ON c.id = t.cliente_id
JOIN produtos p ON t.produto_id = p.id
WHERE p.nome ILIKE '%notebook%'
LIMIT 50;

-- Produtos mais caros:
SELECT nome, preco
FROM produtos
ORDER BY preco DESC
LIMIT 10;
```

Schema disponivel:
{schema_context}

Retorne APENAS o SQL, sem explicacoes, sem markdown, sem ```sql.
"""),
            ("user", """Pergunta original: {question}

Intencao parseada: {parsed_intent}

Gere a query SQL PostgreSQL que responda a pergunta.
LEMBRE-SE: a coluna de valor na tabela transacoes e "valor_total"!
""")
        ])
    
    def generate(self, context: MCPContext) -> MCPContext:
        with tracer.start_span("sql_generator"):
            try:
                logger.info("Generating SQL query")
                
                chain = self.prompt | self.llm
                response = chain.invoke({
                    "question": context.original_question,
                    "schema_context": context.schema_context or "",
                    "parsed_intent": str(context.parsed_intent) if context.parsed_intent else ""
                })
                
                sql_query = self._extract_sql(response.content)
                
                # CORRECAO AUTOMATICA: Substitui nomes de colunas errados
                sql_query = self._fix_column_names(sql_query)
                
                context.generated_sql = sql_query
                context.metadata['sql_generation_method'] = 'gpt4_with_schema_enforcement'
                
                tracer.log_interaction("sql_generator", {
                    "question": context.original_question,
                    "generated_sql": sql_query
                })
                
                logger.info(f"Generated SQL: {sql_query}")
                
            except Exception as e:
                error_msg = f"SQL generation failed: {str(e)}"
                logger.error(error_msg)
                context.add_error("sql_generator", error_msg)
                context.generated_sql = None
                tracer.log_error("sql_generator", e)
        
        return context
    
    def _extract_sql(self, response: str) -> str:
        """Extrai SQL da resposta removendo markdown"""
        sql = response.strip()
        
        # Remove markdown code blocks
        if "```sql" in sql:
            sql = sql.split("```sql")[1].split("```")[0].strip()
        elif "```" in sql:
            sql = sql.split("```")[1].split("```")[0].strip()
        
        # Remove ponto-e-virgula final se houver
        sql = sql.strip()
        if sql.endswith(';'):
            sql = sql[:-1]
        
        return sql
    
    def _fix_column_names(self, sql: str) -> str:
        """CORRECAO AUTOMATICA: Substitui nomes de colunas errados"""
        
        # Lista de correcoes conhecidas
        corrections = {
            # transacoes.valor -> transacoes.valor_total (mas nao transacoes.valor_total)
            r'transacoes\.valor\b(?!_total)': 'transacoes.valor_total',
            # t.valor -> t.valor_total (mas nao t.valor_total)
            r'\bt\.valor\b(?!_total)': 't.valor_total',
            # SUM(valor) -> SUM(valor_total) em contexto de transacoes
            r'SUM\(valor\)': 'SUM(valor_total)',
            r'SUM\(t\.valor\)': 'SUM(t.valor_total)',
            r'SUM\(transacoes\.valor\)': 'SUM(transacoes.valor_total)',
        }
        
        original_sql = sql
        
        for pattern, replacement in corrections.items():
            sql = re.sub(pattern, replacement, sql, flags=re.IGNORECASE)
        
        if sql != original_sql:
            logger.warning(f"SQL corrigido automaticamente:")
            logger.warning(f"  ANTES: {original_sql[:200]}...")
            logger.warning(f"  DEPOIS: {sql[:200]}...")
        
        return sql


sql_generator = SQLGenerator()