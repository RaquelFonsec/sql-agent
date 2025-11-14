import os
import sys
import logging
import uuid
from dotenv import load_dotenv
from typing import TypedDict
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from sqlalchemy import create_engine, text

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.memory.persistent_memory import PersistentMemory

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sql_agent.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    question: str
    user_id: str
    session_id: str
    schema_context: str
    sql_query: str
    validation_result: dict
    execution_result: str
    formatted_response: str
    errors: list


class LangGraphSQLAgent:
    """SQL Agent com LangGraph + Memória Persistente"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4",
            temperature=0,
            openai_api_key=os.getenv('OPENAI_API_KEY')
        )
        
        self.engine = create_engine("postgresql://sql_agent_user:secure_password@localhost/sql_agent_db")
        self.memory = PersistentMemory()
        self.workflow = self._create_workflow()
        logger.info("🧠 LangGraph SQL Agent inicializado com memória persistente")
    
    def _retrieve_schema(self, state: AgentState) -> AgentState:
        print("📋 [1/5] Agente Schema Retriever...")
        
        state['schema_context'] = """
        Tabelas:
        - clientes (id, nome, email, saldo)
        - produtos (id, nome, categoria, preco, estoque)
        - transacoes (id, cliente_id, produto_id, quantidade, valor_total)
        """
        
        return state
    
    def _generate_sql(self, state: AgentState) -> AgentState:
        print("🤖 [2/5] Agente SQL Generator (GPT-4)...")
        
        # 🧠 RECUPERAR HISTÓRICO DO USUÁRIO
        historico = self.memory.get_user_history(state['user_id'], limit=3)
        
        context_historico = ""
        if historico:
            print(f"   💭 Usando contexto de {len(historico)} consultas anteriores")
            context_historico = "\n\nConsultas anteriores deste usuário:\n"
            for h in historico:
                context_historico += f"- {h['question']}\n"
        
        prompt = f"""Schema: {state['schema_context']}
{context_historico}

Pergunta atual: {state['question']}

Gere uma query SQL PostgreSQL. Use apenas SELECT. Retorne apenas o SQL."""

        response = self.llm.invoke(prompt)
        sql = response.content.strip()
        
        if "```sql" in sql:
            sql = sql.split("```sql")[1].split("```")[0].strip()
        elif "```" in sql:
            sql = sql.split("```")[1].split("```")[0].strip()
        
        state['sql_query'] = sql
        print(f"   SQL: {sql[:80]}...")
        
        return state
    
    def _validate_sql(self, state: AgentState) -> AgentState:
        print("✅ [3/5] Agente SQL Validator...")
        
        sql = state['sql_query'].upper()
        is_valid = True
        errors = []
        
        dangerous = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'TRUNCATE']
        for word in dangerous:
            if word in sql:
                is_valid = False
                errors.append(f"Operação perigosa: {word}")
        
        state['validation_result'] = {'is_valid': is_valid, 'errors': errors}
        
        if is_valid:
            print("   ✓ SQL válido e seguro")
        else:
            print(f"   ✗ SQL inválido: {errors}")
        
        return state
    
    def _execute_query(self, state: AgentState) -> AgentState:
        if not state['validation_result']['is_valid']:
            print("⚠️  [4/5] Agente Query Executor (BLOQUEADO)")
            state['execution_result'] = "Query inválida - não executada"
            return state
        
        print("⚡ [4/5] Agente Query Executor...")
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(state['sql_query']))
                rows = result.fetchall()
                columns = result.keys()
                
                data = [dict(zip(columns, row)) for row in rows]
                state['execution_result'] = str(data)
                
                print(f"   ✓ {len(rows)} registro(s) retornado(s)")
                
                # 🧠 SALVAR NA MEMÓRIA
                self.memory.save_interaction(
                    user_id=state['user_id'],
                    session_id=state['session_id'],
                    question=state['question'],
                    sql_query=state['sql_query'],
                    result=state['execution_result'][:200]  # Limitar tamanho
                )
                print("   💾 Salvo na memória persistente")
        
        except Exception as e:
            state['execution_result'] = f"Erro: {e}"
            print(f"   ✗ Erro: {e}")
        
        return state
    
    def _format_response(self, state: AgentState) -> AgentState:
        print("📝 [5/5] Agente Response Formatter...")
        
        response = f"""
PERGUNTA: {state['question']}

SQL GERADO:
{state['sql_query']}

RESULTADO:
{state['execution_result']}
"""
        
        state['formatted_response'] = response
        print("   ✓ Resposta formatada")
        
        return state
    
    def _create_workflow(self):
        workflow = StateGraph(AgentState)
        
        workflow.add_node("retrieve_schema", self._retrieve_schema)
        workflow.add_node("generate_sql", self._generate_sql)
        workflow.add_node("validate_sql", self._validate_sql)
        workflow.add_node("execute_query", self._execute_query)
        workflow.add_node("format_response", self._format_response)
        
        workflow.set_entry_point("retrieve_schema")
        workflow.add_edge("retrieve_schema", "generate_sql")
        workflow.add_edge("generate_sql", "validate_sql")
        workflow.add_edge("validate_sql", "execute_query")
        workflow.add_edge("execute_query", "format_response")
        workflow.add_edge("format_response", END)
        
        return workflow.compile()
    
    def query(self, question: str, user_id: str = "default_user", session_id: str = None):
        """Processar pergunta com memória persistente"""
        
        if session_id is None:
            session_id = str(uuid.uuid4())
        
        print(f"\n{'='*80}")
        print(f"🎯 INICIANDO WORKFLOW COM MEMÓRIA PERSISTENTE")
        print(f"{'='*80}\n")
        print(f"👤 Usuário: {user_id}")
        print(f"🔑 Sessão: {session_id[:16]}...")
        print(f"❓ Pergunta: {question}\n")
        
        initial_state = {
            'question': question,
            'user_id': user_id,
            'session_id': session_id,
            'schema_context': '',
            'sql_query': '',
            'validation_result': {},
            'execution_result': '',
            'formatted_response': '',
            'errors': []
        }
        
        final_state = self.workflow.invoke(initial_state)
        
        print(f"\n{'='*80}")
        print("RESPOSTA FINAL:")
        print(f"{'='*80}")
        print(final_state['formatted_response'])
        
        return final_state
    
    def get_user_history(self, user_id: str, limit: int = 10):
        """Recuperar histórico do usuário"""
        return self.memory.get_user_history(user_id, limit)


def main():
    print("\n" + "="*80)
    print("  🤖 SQL AGENT COM MEMÓRIA PERSISTENTE MULTISESSÃO")
    print("  LangGraph + OpenAI GPT-4 + Memória Automática")
    print("="*80 + "\n")
    
    agent = LangGraphSQLAgent()
    
    # Usuário específico
    user_id = "raquel_fonseca"
    session_id = str(uuid.uuid4())
    
    perguntas = [
        "Quantos clientes temos?",
        "Liste os produtos mais caros",
        "Quais clientes compraram notebook?",
        "Qual o total gasto por cliente?"
    ]
    
    for i, pergunta in enumerate(perguntas, 1):
        print(f"\n{'#'*80}")
        print(f"# CONSULTA {i}/{len(perguntas)}")
        print(f"{'#'*80}")
        
        agent.query(pergunta, user_id=user_id, session_id=session_id)
        
        if i < len(perguntas):
            input("\n⏎ Pressione ENTER para continuar...\n")
    
    # Mostrar histórico
    print("\n" + "="*80)
    print("  📚 HISTÓRICO COMPLETO DO USUÁRIO")
    print("="*80 + "\n")
    
    historico = agent.get_user_history(user_id)
    
    print(f"👤 Usuário: {user_id}")
    print(f"📝 Total de consultas salvas: {len(historico)}\n")
    
    for i, item in enumerate(historico, 1):
        print(f"{i}. {item['question']}")
        print(f"   📅 {item['timestamp']}")
        print()
    
    print("="*80)
    print("  ✅ TODAS AS CONSULTAS FORAM SALVAS NA MEMÓRIA!")
    print("  🧠 Contexto preservado entre sessões")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()

