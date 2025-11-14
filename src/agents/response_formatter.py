from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from src.config.settings import settings
from src.orchestration.mcp_context import MCPContext
from src.observability.tracer import tracer
import logging
import json

logger = logging.getLogger(__name__)


class ResponseFormatter:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.model_name,
            temperature=0.3,
            openai_api_key=settings.openai_api_key
        )
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """Voce e um assistente que formata resultados de queries SQL de forma clara e amigavel.
            
            Sua tarefa e:
            1. Apresentar os dados de forma organizada e legivel
            2. Adicionar contexto relevante baseado na pergunta original
            3. Destacar insights importantes
            4. Usar linguagem natural e acessivel
            5. Se houver muitos resultados, resumir os principais pontos
            
            Formato de saida:
            - Comece com um resumo da resposta
            - Apresente os dados principais
            - Adicione observacoes relevantes se necessario
            """),
            ("user", """Pergunta original: {question}
            
            SQL executado: {sql}
            
            Resultados: {results}
            
            Formate uma resposta clara e util:""")
        ])
    
    def format(self, context: MCPContext) -> MCPContext:
        with tracer.start_span("response_formatter"):
            try:
                if not context.execution_result or not context.execution_result.get('success'):
                    context.formatted_response = self._format_error_response(context)
                    return context
                
                logger.info("Formatting response")
                
                results_str = json.dumps(context.execution_result.get('data', []), indent=2, ensure_ascii=False)
                
                chain = self.prompt | self.llm
                response = chain.invoke({
                    "question": context.original_question,
                    "sql": context.generated_sql,
                    "results": results_str
                })
                
                formatted_response = response.content.strip()
                
                if context.execution_result.get('truncated'):
                    formatted_response += f"\n\nNota: Resultados limitados a {len(context.execution_result['data'])} registros."
                
                context.formatted_response = formatted_response
                
                tracer.log_interaction("response_formatter", {
                    "question": context.original_question,
                    "formatted_response_length": len(formatted_response)
                })
                
                logger.info("Response formatted successfully")
                
            except Exception as e:
                error_msg = f"Response formatting failed: {str(e)}"
                logger.error(error_msg)
                context.add_error("response_formatter", error_msg)
                context.formatted_response = self._format_error_response(context)
                tracer.log_error("response_formatter", e)
        
        return context
    
    def _format_error_response(self, context: MCPContext) -> str:
        error_messages = [error['error'] for error in context.errors]
        
        response = f"Desculpe, nao foi possivel processar sua pergunta:\n\n"
        response += f"Pergunta: {context.original_question}\n\n"
        response += "Erros encontrados:\n"
        for i, error in enumerate(error_messages, 1):
            response += f"{i}. {error}\n"
        
        response += "\nPor favor, reformule sua pergunta ou verifique se os dados solicitados existem."
        
        return response


response_formatter = ResponseFormatter()