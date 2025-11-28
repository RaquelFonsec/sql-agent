from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator
from src.orchestration.mcp_context import MCPContext

# Novos agentes
from src.agents.query_router import query_router
from src.agents.evidence_checker import evidence_checker

# Agentes originais (evoluídos)
from src.agents.nlp_parser import nlp_parser
from src.agents.sql_generator import sql_generator
from src.agents.sql_validator import sql_validator
from src.agents.query_executor import query_executor
from src.agents.response_formatter import response_formatter

from src.rag.schema_retriever import schema_retriever
from src.memory.persistent_memory import memory  # CORRETO: importa 'memory'
from src.observability.tracer import tracer
import logging

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    context: MCPContext
    errors: Annotated[list, operator.add]


def check_cache_node(state: AgentState) -> AgentState:
    """NOVO NODE: Verifica cache semântico"""
    context = state["context"]
    
    with tracer.start_span("check_cache"):
        try:
            cached = memory.check_cache(context.original_question)
            
            if cached:
                context.generated_sql = cached['sql_query']
                context.execution_result = {'success': True, 'data': cached['result'], 'from_cache': True}
                context.metadata['cache_hit'] = True
                
                tracer.log_interaction("check_cache", {"cache_hit": True})
                logger.info("Resultado retornado do cache")
            else:
                context.metadata['cache_hit'] = False
                tracer.log_interaction("check_cache", {"cache_hit": False})
        
        except Exception as e:
            tracer.log_error("check_cache", e)
            context.metadata['cache_hit'] = False
    
    return state


def route_query_node(state: AgentState) -> AgentState:
    """NOVO NODE: Roteia query para estratégia adequada"""
    with tracer.start_span("route_query"):
        try:
            state["context"] = query_router.route(state["context"])
            tracer.log_interaction("route_query", {
                "strategy": state["context"].metadata.get('routing_strategy')
            })
        except Exception as e:
            tracer.log_error("route_query", e)
            state["errors"].append(str(e))
    return state


def retrieve_schema_node(state: AgentState) -> AgentState:
    """NODE EVOLUÍDO: Multi-layer schema retrieval"""
    context = state["context"]
    
    with tracer.start_span("retrieve_schema", {"user_id": context.user_id}):
        try:
            strategy = context.metadata.get('routing_strategy', 'full_pipeline')
            
            schema_data = schema_retriever.retrieve_relevant_schema(
                context.original_question,
                strategy=strategy
            )
            
            context.schema_context = schema_data.get('schema', '')
            context.metadata['schema_metadata'] = schema_data.get('metadata', {})
            context.metadata['schema_statistics'] = schema_data.get('statistics', '')
            
            history = memory.get_session_context(context.user_id, context.session_id)
            context.conversation_history = history
            
            tracer.log_interaction("retrieve_schema", {
                "strategy": strategy,
                "metadata_tables": list(schema_data.get('metadata', {}).keys())
            })
            
        except Exception as e:
            tracer.log_error("retrieve_schema", e)
            state["errors"].append(str(e))
    
    return state


def parse_nlp_node(state: AgentState) -> AgentState:
    """NODE ORIGINAL (mantido)"""
    with tracer.start_span("parse_nlp"):
        try:
            state["context"] = nlp_parser.parse(state["context"])
            tracer.log_interaction("parse_nlp", {"parsed_entities": state["context"].parsed_entities})
        except Exception as e:
            tracer.log_error("parse_nlp", e)
            state["errors"].append(str(e))
    return state


def generate_sql_node(state: AgentState) -> AgentState:
    """NODE ORIGINAL (mantido)"""
    with tracer.start_span("generate_sql"):
        try:
            state["context"] = sql_generator.generate(state["context"])
            tracer.log_interaction("generate_sql", {"sql_preview": state["context"].generated_sql[:200]})
        except Exception as e:
            tracer.log_error("generate_sql", e)
            state["errors"].append(str(e))
    return state


def validate_sql_node(state: AgentState) -> AgentState:
    """NODE EVOLUÍDO: Validação + Otimização + Cost Estimation"""
    with tracer.start_span("validate_sql"):
        try:
            state["context"] = sql_validator.validate(state["context"])
            
            validation = state["context"].validation_result
            tracer.log_interaction("validate_sql", {
                "is_valid": validation.get("is_valid"),
                "estimated_cost": validation.get("estimated_cost"),
                "optimized": validation.get("optimized_sql") != state["context"].generated_sql
            })
        except Exception as e:
            tracer.log_error("validate_sql", e)
            state["errors"].append(str(e))
    return state


def should_execute_query(state: AgentState) -> str:
    """Decisão: executar ou não"""
    if state["context"].metadata.get('cache_hit'):
        return "format_response"
    
    validation_result = state["context"].validation_result
    if validation_result and validation_result.get("is_valid"):
        return "execute"
    return "format_error"


def execute_query_node(state: AgentState) -> AgentState:
    """NODE EVOLUÍDO: Execução com streaming"""
    with tracer.start_span("execute_query"):
        try:
            state["context"] = query_executor.execute(state["context"])
            
            result = state["context"].execution_result
            tracer.log_interaction("execute_query", {
                "rows_count": len(result.get('data', [])),
                "truncated": result.get('truncated', False)
            })
        except Exception as e:
            tracer.log_error("execute_query", e)
            state["errors"].append(str(e))
    return state


def format_response_node(state: AgentState) -> AgentState:
    """NODE ORIGINAL (mantido)"""
    with tracer.start_span("format_response"):
        try:
            state["context"] = response_formatter.format(state["context"])
            
            tracer.log_interaction("format_response", {
                "formatted_preview": str(state["context"].formatted_response)[:200]
            })

            memory.save_interaction(
                user_id=state["context"].user_id,
                session_id=state["context"].session_id,
                question=state["context"].original_question,
                sql_query=state["context"].generated_sql,
                result=state["context"].execution_result,
                metadata=state["context"].metadata,
            )
        except Exception as e:
            tracer.log_error("format_response", e)
            state["errors"].append(str(e))
    return state


def check_evidence_node(state: AgentState) -> AgentState:
    """NOVO NODE: Verifica evidências"""
    with tracer.start_span("check_evidence"):
        try:
            state["context"] = evidence_checker.check(state["context"])
            
            tracer.log_interaction("check_evidence", {
                "corrected": state["context"].metadata.get('response_corrected', False)
            })
        except Exception as e:
            tracer.log_error("check_evidence", e)
    return state


def create_workflow() -> StateGraph:
    """Workflow completo evoluído"""
    workflow = StateGraph(AgentState)
    
    workflow.add_node("check_cache", check_cache_node)
    workflow.add_node("route_query", route_query_node)
    workflow.add_node("check_evidence", check_evidence_node)
    
    workflow.add_node("retrieve_schema", retrieve_schema_node)
    workflow.add_node("parse_nlp", parse_nlp_node)
    workflow.add_node("generate_sql", generate_sql_node)
    workflow.add_node("validate_sql", validate_sql_node)
    workflow.add_node("execute_query", execute_query_node)
    workflow.add_node("format_response", format_response_node)
    
    workflow.set_entry_point("check_cache")
    
    workflow.add_conditional_edges(
        "check_cache",
        lambda state: "format_response" if state["context"].metadata.get('cache_hit') else "route_query"
    )
    
    workflow.add_edge("route_query", "retrieve_schema")
    workflow.add_edge("retrieve_schema", "parse_nlp")
    workflow.add_edge("parse_nlp", "generate_sql")
    workflow.add_edge("generate_sql", "validate_sql")
    
    workflow.add_conditional_edges(
        "validate_sql",
        should_execute_query,
        {"execute": "execute_query", "format_error": "format_response"},
    )
    
    workflow.add_edge("execute_query", "format_response")
    workflow.add_edge("format_response", "check_evidence")
    workflow.add_edge("check_evidence", END)
    
    return workflow.compile()


sql_agent_workflow = create_workflow()


def run_single_query(question: str, user_id: str = "raquel_fonseca"):
    """
    Executa uma unica query customizada
    
    Args:
        question: Pergunta em linguagem natural
        user_id: ID do usuario
    
    Returns:
        dict com resultado
    """
    import uuid
    from datetime import datetime
    
    logger.info("="*80)
    logger.info("  EXECUTANDO QUERY CUSTOMIZADA")
    logger.info("="*80)
    logger.info("Usuario: %s", user_id)
    logger.info("Pergunta: %s", question)
    
    context = MCPContext(
        user_id=user_id,
        session_id=str(uuid.uuid4()),
        original_question=question,
        timestamp=datetime.utcnow()
    )
    
    initial_state = {
        "context": context,
        "errors": []
    }
    
    try:
        result = sql_agent_workflow.invoke(initial_state)
        final_context = result["context"]
        
        return {
            "formatted_response": final_context.formatted_response or "Nao foi possivel gerar resposta",
            "sql": final_context.generated_sql or "N/A",
            "from_cache": final_context.metadata.get("cache_hit", False),
            "execution_time": final_context.metadata.get("execution_time", 0),
            "evidence_status": final_context.metadata.get("evidence_check", {}).get("is_correct", "N/A"),
            "category": final_context.metadata.get("query_category", "N/A"),
            "strategy": final_context.metadata.get("routing_strategy", "N/A"),
        }
    
    except Exception as e:
        logger.error("Erro ao executar query: %s", e)
        return {
            "formatted_response": f"Erro: {str(e)}",
            "sql": "N/A",
            "from_cache": False,
            "execution_time": 0,
            "evidence_status": "Erro",
            "category": "N/A",
            "strategy": "N/A",
        }


def main():
    """Função principal para executar o workflow completo"""
    import uuid
    from datetime import datetime
    
    print("\n" + "="*80)
    print("  SQL AGENT - ARQUITETURA EVOLUIDA")
    print("  Multi-Agente com Router + Evidence Checker")
    print("="*80 + "\n")
    
    questions = [
        "Quantos clientes temos?",
        "Liste os produtos mais caros",
        "Quais clientes compraram notebook?",
        "Qual o total gasto por cliente?"
    ]
    
    user_id = "raquel_fonseca"
    session_id = str(uuid.uuid4())
    
    print(f"Usuario: {user_id}")
    print(f"Sessao: {session_id[:16]}...")
    print(f"Total de perguntas: {len(questions)}\n")
    
    for i, question in enumerate(questions, 1):
        print("\n" + "#"*80)
        print(f"# CONSULTA {i}/{len(questions)}")
        print("#"*80 + "\n")
        print(f"Pergunta: {question}\n")
        
        initial_state = {
            "context": MCPContext(
                user_id=user_id,
                session_id=session_id,
                original_question=question
            ),
            "errors": []
        }
        
        try:
            print("Executando workflow...\n")
            final_state = sql_agent_workflow.invoke(initial_state)
            
            context = final_state["context"]
            
            print("="*80)
            print("RESULTADO FINAL:")
            print("="*80 + "\n")
            
            if context.formatted_response:
                print(context.formatted_response)
            else:
                print("Nenhuma resposta gerada")
            
            print("\n" + "-"*80)
            print("METADADOS:")
            print("-"*80)
            
            if context.metadata.get('cache_hit'):
                print("CACHE: Resultado retornado do cache (instantaneo)")
            
            if context.metadata.get('query_category'):
                print(f"Categoria detectada: {context.metadata['query_category']}")
                print(f"Estrategia usada: {context.metadata['routing_strategy']}")
            
            if context.generated_sql:
                print(f"SQL gerado: {context.generated_sql[:100]}...")
            
            if context.validation_result:
                validation = context.validation_result
                if validation.get('estimated_cost'):
                    print(f"Custo estimado: {validation['estimated_cost']}")
                if validation.get('estimated_rows'):
                    print(f"Linhas estimadas: {validation['estimated_rows']}")
            
            if context.metadata.get('evidence_check'):
                evidence = context.metadata['evidence_check']
                if evidence.get('is_correct'):
                    print("Evidencias: Validadas - sem alucinacoes")
                else:
                    print("Evidencias: Resposta corrigida automaticamente")
                    if evidence.get('issues'):
                        print(f"Problemas detectados: {len(evidence['issues'])}")
            
            if final_state.get("errors"):
                print(f"\nErros encontrados: {len(final_state['errors'])}")
                for error in final_state["errors"]:
                    print(f"   - {error}")
            
        except Exception as e:
            print(f"\nERRO durante execucao: {e}")
            import traceback
            traceback.print_exc()
        
        if i < len(questions):
            input("\n\nPressione ENTER para proxima consulta...\n")
    
    print("\n" + "="*80)
    print("  WORKFLOW CONCLUIDO COM SUCESSO")
    print("="*80)
    
    try:
        stats = memory.get_cache_statistics()
        
        print("\nESTATISTICAS DO CACHE:")
        print(f"   Queries cacheadas: {stats.get('total_cached_queries', 0)}")
        print(f"   Cache hits: {stats.get('total_cache_hits', 0)}")
        print(f"   Taxa de acerto: {stats.get('cache_hit_rate', '0%')}")
    except:
        pass
    
    print("\nSistema pronto para escalar para milhoes de dados!")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
