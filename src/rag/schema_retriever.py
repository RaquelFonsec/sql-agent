from typing import List, Dict
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain.docstore.document import Document
from src.config.settings import settings
import logging

logger = logging.getLogger(__name__)


class SchemaRetriever:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(openai_api_key=settings.openai_api_key)
        self.vectorstore = None
        self._init_vectorstore()
    
    def _init_vectorstore(self):
        schema_docs = self._create_schema_documents()
        self.vectorstore = FAISS.from_documents(schema_docs, self.embeddings)
        logger.info("Schema vector store initialized")
    
    def _create_schema_documents(self) -> List[Document]:
        documents = [
            Document(
                page_content="""
                Tabela: clientes
                Colunas:
                - id (INTEGER, PRIMARY KEY): Identificador unico do cliente
                - nome (VARCHAR): Nome completo do cliente
                - email (VARCHAR, UNIQUE): Email do cliente
                - saldo (FLOAT): Saldo disponivel da conta do cliente
                - data_cadastro (TIMESTAMP): Data de cadastro do cliente
                
                Relacionamentos: Um cliente pode ter multiplas transacoes
                """,
                metadata={'table': 'clientes'}
            ),
            Document(
                page_content="""
                Tabela: produtos
                Colunas:
                - id (INTEGER, PRIMARY KEY): Identificador unico do produto
                - nome (VARCHAR): Nome do produto
                - categoria (VARCHAR): Categoria do produto (Eletronicos, Perifericos)
                - preco (FLOAT): Preco unitario do produto
                - estoque (INTEGER): Quantidade em estoque
                - descricao (TEXT): Descricao detalhada do produto
                
                Relacionamentos: Um produto pode estar em multiplas transacoes
                """,
                metadata={'table': 'produtos'}
            ),
            Document(
                page_content="""
                Tabela: transacoes
                Colunas:
                - id (INTEGER, PRIMARY KEY): Identificador unico da transacao
                - cliente_id (INTEGER, FOREIGN KEY): Referencia ao cliente
                - produto_id (INTEGER, FOREIGN KEY): Referencia ao produto
                - quantidade (INTEGER): Quantidade comprada
                - valor_total (FLOAT): Valor total da transacao
                - data_transacao (TIMESTAMP): Data da transacao
                
                Relacionamentos:
                - Cada transacao pertence a um cliente (JOIN com clientes via cliente_id)
                - Cada transacao se refere a um produto (JOIN com produtos via produto_id)
                """,
                metadata={'table': 'transacoes'}
            ),
            Document(
                page_content="""
                Exemplos de queries comuns:
                
                1. Listar clientes que compraram um produto especifico:
                SELECT DISTINCT c.nome, c.email
                FROM clientes c
                JOIN transacoes t ON c.id = t.cliente_id
                JOIN produtos p ON t.produto_id = p.id
                WHERE p.nome = 'Notebook';
                
                2. Calcular total gasto por cliente:
                SELECT c.nome, SUM(t.valor_total) as total_gasto
                FROM clientes c
                JOIN transacoes t ON c.id = t.cliente_id
                GROUP BY c.id, c.nome;
                
                3. Clientes com saldo suficiente para comprar um produto:
                SELECT c.nome, c.saldo, p.nome as produto, p.preco
                FROM clientes c
                CROSS JOIN produtos p
                WHERE c.saldo >= p.preco AND p.nome = 'Smartphone';
                """,
                metadata={'type': 'examples'}
            )
        ]
        return documents
    
    def retrieve_relevant_schema(self, question: str, k: int = 3) -> str:
        if not self.vectorstore:
            return ""
        
        try:
            docs = self.vectorstore.similarity_search(question, k=k)
            context = "\n\n".join([doc.page_content for doc in docs])
            logger.info(f"Retrieved {len(docs)} relevant schema documents")
            return context
        except Exception as e:
            logger.error(f"Error retrieving schema context: {e}")
            return ""


schema_retriever = SchemaRetriever()