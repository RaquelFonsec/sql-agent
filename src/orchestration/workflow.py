from langgraph.graph import StateGraph, END
from typing import TypedDict, Annotated
import operator
from src.orchestration.mcp_context import MCPContext
from src.agents.nlp_parser import nlp_parser
from src.agents.sql_generator import sql_generator
from src.agents.sql_validator import sql_validator
from src.agents.query_executor import query_executor
from src.agents.response_formatter import response_formatter
from src.rag.schema_retriever import schema_retriever
from src.memory.persistent_memory import memory
from src.observability.tracer import tracer
import logging

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    context: MCPContext
    errors: Annotated[list, operator.add]


def retrieve_schema_node(state: AgentState) -> AgentState:
    context = state["context"]
    with tracer.start_span("retrieve_schema", {"user_id": context.user_id}):
        try:
            context.schema_context = schema_retriever.retrieve_relevant_schema(context.original_question)
            history = memory.get_session_context(context.user_id, context.session_id)
            context.conversation_history = history
            tracer.log_interaction("retrieve_schema", {"schema_keys": list(context.schema_context.keys())})
        except Exception as e:
            tracer.log_error("retrieve_schema", e)
            state["errors"].append(str(e))
    return state


def parse_nlp_node(state: AgentState) -> AgentState:
    with tracer.start_span("parse_nlp"):
        try:
            state["context"] = nlp_parser.parse(state["context"])
            tracer.log_interaction("parse_nlp", {"parsed_entities": state["context"].parsed_entities})
        except Exception as e:
            tracer.log_error("parse_nlp", e)
            state["errors"].append(str(e))
    return state


def generate_sql_node(state: AgentState) -> AgentState:
    with tracer.start_span("generate_sql"):
        try:
            state["context"] = sql_generator.generate(state["context"])
            tracer.log_interaction("generate_sql", {"sql_preview": state["context"].generated_sql[:200]})
        except Exception as e:
            tracer.log_error("generate_sql", e)
            state["errors"].append(str(e))
    return state


def validate_sql_node(state: AgentState) -> AgentState:
    with tracer.start_span("validate_sql"):
        try:
            state["context"] = sql_validator.validate(state["context"])
            tracer.log_interaction("validate_sql", {"is_valid": state["context"].validation_result.get("is_valid")})
        except Exception as e:
            tracer.log_error("validate_sql", e)
            state["errors"].append(str(e))
    return state


def should_execute_query(state: AgentState) -> str:
    validation_result = state["context"].validation_result
    if validation_result and validation_result.get("is_valid"):
        return "execute"
    return "format_error"


def execute_query_node(state: AgentState) -> AgentState:
    with tracer.start_span("execute_query"):
        try:
            state["context"] = query_executor.execute(state["context"])
            tracer.log_interaction("execute_query", {"rows_count": len(state["context"].execution_result or [])})
        except Exception as e:
            tracer.log_error("execute_query", e)
            state["errors"].append(str(e))
    return state


def format_response_node(state: AgentState) -> AgentState:
    with tracer.start_span("format_response"):
        try:
            state["context"] = response_formatter.format(state["context"])
            tracer.log_interaction("format_response", {"formatted_preview": str(state["context"].formatted_response)[:200]})

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


def create_workflow() -> StateGraph:
    workflow = StateGraph(AgentState)
    
    workflow.add_node("retrieve_schema", retrieve_schema_node)
    workflow.add_node("parse_nlp", parse_nlp_node)
    workflow.add_node("generate_sql", generate_sql_node)
    workflow.add_node("validate_sql", validate_sql_node)
    workflow.add_node("execute_query", execute_query_node)
    workflow.add_node("format_response", format_response_node)
    
    workflow.set_entry_point("retrieve_schema")
    
    workflow.add_edge("retrieve_schema", "parse_nlp")
    workflow.add_edge("parse_nlp", "generate_sql")
    workflow.add_edge("generate_sql", "validate_sql")
    
    workflow.add_conditional_edges(
        "validate_sql",
        should_execute_query,
        {"execute": "execute_query", "format_error": "format_response"},
    )
    
    workflow.add_edge("execute_query", "format_response")
    workflow.add_edge("format_response", END)
    
    return workflow.compile()


sql_agent_workflow = create_workflow()
