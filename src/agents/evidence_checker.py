from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate  # ✅ CORRETO
from src.config.settings import settings
from src.orchestration.mcp_context import MCPContext
from src.observability.tracer import tracer
import logging
import json

logger = logging.getLogger(__name__)


class EvidenceChecker:
    """AGENTE 6: Verificador de evidências"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4",
            temperature=0,
            openai_api_key=settings.openai_api_key
        )
        
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """Você é um auditor de respostas SQL.
            
            Sua missão: verificar se a resposta formatada está 100% baseada nos dados reais.
            
            REGRAS:
            1. Compare a resposta com os dados JSON
            2. Se houver informação que não está nos dados, marque como INCORRETO
            3. Se números não batem, marque como INCORRETO
            
            Retorne JSON:
            {{
                "is_correct": true/false,
                "issues": ["lista de problemas"],
                "corrected_response": "resposta corrigida (se necessário)"
            }}
            """),
            ("user", """Pergunta: {question}

SQL: {sql}

Dados REAIS: {data}

Resposta formatada: {formatted_response}

Audite:""")
        ])
    
    def check(self, context: MCPContext) -> MCPContext:
        """Verifica evidências da resposta"""
        with tracer.start_span("evidence_checker"):
            try:
                if not context.formatted_response:
                    return context
                
                logger.info("Checking evidence in response")
                
                data_str = json.dumps(
                    context.execution_result.get('data', []),
                    indent=2,
                    ensure_ascii=False
                )
                
                chain = self.prompt | self.llm
                response = chain.invoke({
                    "question": context.original_question,
                    "sql": context.generated_sql,
                    "data": data_str,
                    "formatted_response": context.formatted_response
                })
                
                audit_result = self._parse_audit_result(response.content)
                context.metadata['evidence_check'] = audit_result
                
                if not audit_result.get('is_correct'):
                    logger.warning(f"Evidence issues: {audit_result.get('issues')}")
                    corrected = audit_result.get('corrected_response')
                    if corrected:
                        context.formatted_response = corrected
                        context.metadata['response_corrected'] = True
                
                tracer.log_interaction("evidence_checker", {
                    "is_correct": audit_result.get('is_correct'),
                    "issues_count": len(audit_result.get('issues', []))
                })
                
                logger.info(f"Evidence check: {'✅ OK' if audit_result.get('is_correct') else '❌ CORRIGIDO'}")
                
            except Exception as e:
                logger.error(f"Evidence check failed: {e}")
                tracer.log_error("evidence_checker", e)
        
        return context
    
    def _parse_audit_result(self, content: str) -> dict:
        """Parse JSON do LLM"""
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            return json.loads(content.strip())
        except:
            return {
                "is_correct": True,
                "issues": [],
                "corrected_response": None
            }


evidence_checker = EvidenceChecker()
