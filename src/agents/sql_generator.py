from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from src.config.settings import settings
from src.orchestration.mcp_context import MCPContext
from src.observability.tracer import tracer
import logging

logger = logging.getLogger(__name__)


class SQLGenerator:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.model_name,
            temperature=settings.temperature,
            openai_api_key=settings.openai_api_key
        )
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """Voce e um especialista em PostgreSQL.
            Gere uma query SQL segura, otimizada e correta baseada na intencao do usuario.
            
            REGRAS IMPORTANTES:
            1. Use apenas SELECT para leitura de dados
            2. Use JOINs apropriados quando necessario
            3. Use aliases para melhor legibilidade
            4. Use parametrizacao para prevenir SQL Injection
            5. Adicione LIMIT quando apropriado para evitar retornos excessivos
            6. Use indices quando disponiveis
            7. Prefira INNER JOIN a menos que especificado diferente
            
            Retorne APENAS a query SQL, sem explicacoes ou markdown.
            
            Schema disponivel:
            {schema_context}
            """),
            ("user", """Pergunta original: {question}
            
            Intencao parseada: {parsed_intent}
            
            Gere a query SQL:""")
        ])
    
    def generate(self, context: MCPContext) -> MCPContext:
        with tracer.start_span("sql_generator"):
            try:
                logger.info("Generating SQL query")
                
                chain = self.prompt | self.llm
                response = chain.invoke({
                    "question": context.original_question,
                    "schema_context": context.schema_context or "",
                    "parsed_intent": str(context.parsed_intent)
                })
                
                sql_query = response.content.strip()
                
                if "```sql" in sql_query:
                    sql_query = sql_query.split("```sql")[1].split("```")[0].strip()
                elif "```" in sql_query:
                    sql_query = sql_query.split("```")[1].split("```")[0].strip()
                
                context.generated_sql = sql_query
                
                tracer.log_interaction("sql_generator", {
                    "question": context.original_question,
                    "generated_sql": sql_query
                })
                
                logger.info(f"Generated SQL: {sql_query}")
                
            except Exception as e:
                error_msg = f"SQL generation failed: {str(e)}"
                logger.error(error_msg)
                context.add_error("sql_generator", error_msg)
                tracer.log_error("sql_generator", e)
        
        return context


sql_generator = SQLGenerator()