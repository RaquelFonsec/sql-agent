from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate  # ✅ CORRETO
from src.config.settings import settings
from src.orchestration.mcp_context import MCPContext
from src.observability.tracer import tracer
import logging

logger = logging.getLogger(__name__)


class QueryRouter:
    """AGENTE 0: Roteador inteligente de queries"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-3.5-turbo",
            temperature=0,
            openai_api_key=settings.openai_api_key
        )
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """Você é um classificador de queries SQL.
            
            Classifique a pergunta em UMA categoria:
            
            1. STRUCTURAL: Perguntas sobre estrutura do banco
            2. AGGREGATION: Queries com agregações simples
            3. SEARCH: Buscas com filtros complexos
            4. ANALYTICS: Análises complexas, múltiplos JOINs
            
            Retorne APENAS a categoria (uma palavra em maiúsculo).
            """),
            ("user", "Pergunta: {question}\n\nCategoria:")
        ])
    
    def route(self, context: MCPContext) -> MCPContext:
        """Classifica a query e define a estratégia"""
        with tracer.start_span("query_router"):
            try:
                chain = self.prompt | self.llm
                response = chain.invoke({"question": context.original_question})
                
                category = response.content.strip().upper()
                
                strategies = {
                    "STRUCTURAL": "schema_only",
                    "AGGREGATION": "sql_direct",
                    "SEARCH": "filtered_rag",
                    "ANALYTICS": "full_pipeline"
                }
                
                strategy = strategies.get(category, "full_pipeline")
                
                context.metadata['query_category'] = category
                context.metadata['routing_strategy'] = strategy
                
                tracer.log_interaction("query_router", {
                    "question": context.original_question,
                    "category": category,
                    "strategy": strategy
                })
                
                logger.info(f"Query routed: {category} -> {strategy}")
                
            except Exception as e:
                logger.error(f"Routing error: {e}")
                context.metadata['routing_strategy'] = "full_pipeline"
                tracer.log_error("query_router", e)
        
        return context


query_router = QueryRouter()
