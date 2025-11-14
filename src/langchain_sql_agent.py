import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from langchain_experimental.sql import SQLDatabaseChain
from langchain_core.prompts import PromptTemplate
import logging

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LangChainSQLAgent:
    """SQL Agent com LangChain + SQLDatabaseChain"""
    
    def __init__(self):
        # Conectar ao banco
        database_url = "postgresql://sql_agent_user:secure_password@localhost/sql_agent_db"
        self.db = SQLDatabase.from_uri(database_url)
        
        # Configurar LLM
        self.llm = ChatOpenAI(
            model="gpt-4",
            temperature=0,
            openai_api_key=os.getenv('OPENAI_API_KEY')
        )
        
        # Criar prompt customizado
        self.custom_prompt = PromptTemplate(
            input_variables=["input", "table_info", "top_k"],
            template="""Você é um especialista em SQL PostgreSQL.

Dadas as seguintes tabelas:
{table_info}

Tarefa: Crie uma query SQL para responder à pergunta do usuário.

Regras importantes:
- Use apenas SELECT (nunca DELETE, DROP, UPDATE, INSERT)
- Use ILIKE para buscas case-insensitive em strings
- Limite resultados com LIMIT {top_k}
- Use JOINs quando necessário relacionar tabelas
- Use aliases para melhor legibilidade

Pergunta: {input}

SQL Query:"""
        )
        
        # Criar chain SQL
        self.db_chain = SQLDatabaseChain.from_llm(
            llm=self.llm,
            db=self.db,
            prompt=self.custom_prompt,
            verbose=True,
            return_intermediate_steps=True,
            top_k=10
        )
    
    def query(self, question: str):
        """Converter pergunta em SQL e executar"""
        try:
            print(f"\n{'='*80}")
            print(f"PERGUNTA: {question}")
            print(f"{'='*80}\n")
            
            logger.info(f"Processando: {question}")
            
            # Executar chain
            result = self.db_chain(question)
            
            print(f"\n✅ SQL Gerado:")
            print(f"   {result['intermediate_steps'][0]}\n")
            
            print(f"✅ Resultado:")
            print(f"   {result['result']}\n")
            
            return {
                'success': True,
                'question': question,
                'sql': result['intermediate_steps'][0],
                'result': result['result']
            }
            
        except Exception as e:
            logger.error(f"Erro: {e}")
            print(f"\n❌ Erro: {e}\n")
            return {
                'success': False,
                'question': question,
                'error': str(e)
            }


def main():
    print("\n" + "="*80)
    print("  🤖 SQL AGENT COM LANGCHAIN + OPENAI GPT-4")
    print("="*80 + "\n")
    
    agent = LangChainSQLAgent()
    
    perguntas = [
        "Quantos clientes temos cadastrados?",
        "Quais clientes compraram um notebook?",
        "Qual é o produto mais caro?",
        "Mostre o total de vendas por categoria de produto",
        "Quais clientes gastaram mais de 3000 reais?",
        "Qual cliente tem o maior saldo?"
    ]
    
    for i, pergunta in enumerate(perguntas, 1):
        print(f"\n{'#'*80}")
        print(f"# CONSULTA {i}/{len(perguntas)}")
        print(f"{'#'*80}")
        
        resultado = agent.query(pergunta)
        
        if i < len(perguntas):
            input("\n⏎ Pressione ENTER para continuar...\n")
    
    print("\n" + "="*80)
    print("  ✅ DEMONSTRAÇÃO LANGCHAIN CONCLUÍDA!")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
