from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from src.config.settings import settings
from src.orchestration.mcp_context import MCPContext
from src.observability.tracer import tracer
import logging
import json

logger = logging.getLogger(__name__)


class NLPParser:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.model_name,
            temperature=settings.temperature,
            openai_api_key=settings.openai_api_key
        )
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """Voce e um especialista em analise de linguagem natural para queries SQL.
            Sua tarefa e extrair a intencao do usuario e identificar entidades relevantes.
            
            Retorne um JSON com:
            - intent: tipo de operacao (SELECT, INSERT, UPDATE, DELETE, AGGREGATE, JOIN)
            - entities: entidades mencionadas (tabelas, colunas, valores)
            - filters: filtros a serem aplicados
            - aggregations: agregacoes necessarias (SUM, COUNT, AVG, etc)
            - joins: tabelas que precisam ser relacionadas
            
            Exemplo de pergunta: "Quais clientes compraram um Notebook?"
            Resposta esperada:
            {{
                "intent": "JOIN",
                "entities": {{"tables": ["clientes", "transacoes", "produtos"], "product_name": "Notebook"}},
                "filters": {{"produto.nome": "Notebook"}},
                "aggregations": [],
                "joins": ["clientes-transacoes", "transacoes-produtos"]
            }}
            """),
            ("user", "{question}\n\nContexto do schema:\n{schema_context}")
        ])
    
    def parse(self, context: MCPContext) -> MCPContext:
        with tracer.start_span("nlp_parser"):
            try:
                logger.info(f"Parsing question: {context.original_question}")
                
                chain = self.prompt | self.llm
                response = chain.invoke({
                    "question": context.original_question,
                    "schema_context": context.schema_context or "Schema nao disponivel"
                })
                
                parsed_content = response.content
                if "```json" in parsed_content:
                    parsed_content = parsed_content.split("```json")[1].split("```")[0].strip()
                
                context.parsed_intent = json.loads(parsed_content)
                
                tracer.log_interaction("nlp_parser", {
                    "question": context.original_question,
                    "parsed_intent": context.parsed_intent
                })
                
                logger.info(f"Successfully parsed intent: {context.parsed_intent['intent']}")
                
            except Exception as e:
                error_msg = f"NLP parsing failed: {str(e)}"
                logger.error(error_msg)
                context.add_error("nlp_parser", error_msg)
                tracer.log_error("nlp_parser", e)
        
        return context


nlp_parser = NLPParser()