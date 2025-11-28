from typing import List, Dict, Optional
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain.docstore.document import Document
from src.config.settings import settings
import logging
import json

logger = logging.getLogger(__name__)


class MultiLayerSchemaRetriever:
    """AGENTE 1 EVOLUÍDO: RAG em 3 camadas
    
    Layer 1: Metadados (sempre em memória)
    Layer 2: Schema RAG (FAISS)
    Layer 3: Estatísticas do banco
    """
    
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(openai_api_key=settings.openai_api_key)
        self.vectorstore = None
        
        # LAYER 1: Metadados (lightweight, sempre disponível)
        self.metadata = {
            "clientes": {
                "count": 5,  # Em produção: 3_000_000
                "size_mb": 1,  # Em produção: 500 MB
                "has_index": True,
                "indexed_columns": ["id", "email"],
                "date_range": "2020-2025"
            },
            "transacoes": {
                "count": 10,  # Em produção: 150_000_000
                "size_mb": 2,  # Em produção: 5 GB
                "has_index": True,
                "indexed_columns": ["cliente_id", "produto_id", "data_transacao"],
                "date_range": "2020-2025"
            },
            "produtos": {
                "count": 6,  # Em produção: 25_000
                "size_mb": 0.1,
                "has_index": True,
                "indexed_columns": ["id", "categoria"]
            }
        }
        
        # LAYER 3: Estatísticas pré-computadas
        self.query_statistics = {
            "frequent_queries": [
                "SELECT COUNT(*) FROM clientes",
                "SELECT SUM(valor_total) FROM transacoes"
            ],
            "slow_patterns": [
                "SELECT * FROM transacoes",  # Sem LIMIT
                "JOIN sem WHERE"
            ],
            "optimal_limits": {
                "clientes": 1000,
                "transacoes": 100,
                "produtos": 500
            }
        }
        
        self._init_vectorstore()
    
    def _init_vectorstore(self):
        """LAYER 2: Schema documents (FAISS)"""
        schema_docs = self._create_schema_documents()
        self.vectorstore = FAISS.from_documents(schema_docs, self.embeddings)
        logger.info("Multi-layer schema retriever initialized")
    
    def _create_schema_documents(self) -> List[Document]:
        """Documentos com descrições detalhadas"""
        documents = [
            Document(
                page_content="""
                Tabela: clientes
                Colunas:
                - id (INTEGER, PRIMARY KEY, INDEXED): Identificador único
                - nome (VARCHAR): Nome completo
                - email (VARCHAR, UNIQUE, INDEXED): Email único
                - saldo (FLOAT): Saldo disponível (>= 0)
                - data_cadastro (TIMESTAMP): Data de registro
                
                Cardinalidade: 5 registros (em produção: 3M)
                Índices: PRIMARY KEY (id), UNIQUE (email)
                Relacionamentos: 1:N com transacoes
                
                Queries otimizadas:
                - Busca por email: O(1) devido a índice UNIQUE
                - Busca por id: O(1) due a PRIMARY KEY
                - Filtro por saldo: O(N) - considere adicionar índice
                """,
                metadata={'table': 'clientes', 'layer': 'schema'}
            ),
            Document(
                page_content="""
                Tabela: produtos
                Colunas:
                - id (INTEGER, PRIMARY KEY, INDEXED)
                - nome (VARCHAR)
                - categoria (VARCHAR, INDEXED): Categorias existentes
                - preco (FLOAT, >= 0)
                - estoque (INTEGER, >= 0)
                - descricao (TEXT)
                
                Cardinalidade: 6 produtos (em produção: 25K)
                Índices: PRIMARY KEY (id), INDEX (categoria)
                
                Valores típicos de categoria:
                - "Eletrônicos"
                - "Periféricos"
                
                Queries otimizadas:
                - Filtro por categoria: O(log N) devido a índice
                - Ordenação por preco: Rápida (coluna numérica)
                """,
                metadata={'table': 'produtos', 'layer': 'schema'}
            ),
            Document(
                page_content="""
                Tabela: transacoes (TABELA GRANDE - CUIDADO!)
                Colunas:
                - id (INTEGER, PRIMARY KEY)
                - cliente_id (INTEGER, FK, INDEXED)
                - produto_id (INTEGER, FK, INDEXED)
                - quantidade (INTEGER, > 0)
                - valor_total (FLOAT, >= 0)
                - data_transacao (TIMESTAMP, INDEXED)
                
                Cardinalidade: 10 registros (em produção: 150M)
                Índices: PKG (id), INDEX (cliente_id), INDEX (produto_id), INDEX (data_transacao)
                
                ⚠️ AVISOS:
                - NUNCA use SELECT * sem LIMIT
                - SEMPRE filtre por data_transacao quando possível
                - Use JOINs com WHERE para reduzir resultado
                - Limite padrão recomendado: 100 linhas
                
                Queries otimizadas:
                - Agregações com GROUP BY: muito rápidas
                - Filtros por cliente_id: O(log N) devido a índice
                - Range de datas: O(log N) devido a índice
                """,
                metadata={'table': 'transacoes', 'layer': 'schema'}
            ),
            Document(
                page_content="""
                PADRÕES DE QUERIES OTIMIZADAS:
                
                1. Contar clientes:
                   SELECT COUNT(*) FROM clientes;
                   Custo: Baixo (tabela pequena)
                
                2. Total por cliente (COM LIMITE):
                   SELECT c.nome, SUM(t.valor_total) as total
                   FROM clientes c
                   JOIN transacoes t ON c.id = t.cliente_id
                   WHERE t.data_transacao >= '2024-01-01'
                   GROUP BY c.id, c.nome
                   LIMIT 100;
                   Custo: Médio (uso de índices)
                
                3. Clientes que compraram produto X:
                   SELECT DISTINCT c.nome
                   FROM clientes c
                   JOIN transacoes t ON c.id = t.cliente_id
                   JOIN produtos p ON t.produto_id = p.id
                   WHERE p.nome ILIKE '%notebook%'
                   LIMIT 50;
                   Custo: Médio (3 tabelas, mas com índices)
                
                ⚠️ EVITE:
                - SELECT * FROM transacoes (150M linhas!)
                - JOINs sem WHERE
                - ORDER BY em colunas não indexadas
                """,
                metadata={'type': 'examples', 'layer': 'patterns'}
            )
        ]
        return documents
    
    def retrieve_relevant_schema(self, question: str, strategy: str = "full") -> Dict:
        """Retrieve com estratégia adaptativa"""
        try:
            # LAYER 1: Sempre retorna metadados
            metadata_context = self._filter_metadata_by_question(question)
            
            # LAYER 2: Schema RAG (só se necessário)
            schema_context = ""
            if strategy in ["full_pipeline", "filtered_rag"]:
                docs = self.vectorstore.similarity_search(question, k=2)
                schema_context = "\n\n".join([doc.page_content for doc in docs])
            
            # LAYER 3: Estatísticas (para queries analíticas)
            stats_context = ""
            if strategy in ["full_pipeline", "analytics"]:
                stats_context = self._get_relevant_statistics(question)
            
            result = {
                "metadata": metadata_context,
                "schema": schema_context,
                "statistics": stats_context,
                "strategy_used": strategy
            }
            
            logger.info(f"Retrieved schema (strategy: {strategy})")
            return result
            
        except Exception as e:
            logger.error(f"Error in schema retrieval: {e}")
            return {"metadata": {}, "schema": "", "statistics": ""}
    
    def _filter_metadata_by_question(self, question: str) -> Dict:
        """Filtra metadados relevantes baseado na pergunta"""
        question_lower = question.lower()
        
        relevant_tables = []
        if "cliente" in question_lower:
            relevant_tables.append("clientes")
        if "produto" in question_lower:
            relevant_tables.append("produtos")
        if "transacao" in question_lower or "compra" in question_lower or "venda" in question_lower:
            relevant_tables.append("transacoes")
        
        # Se nenhuma tabela mencionada, retorna todas
        if not relevant_tables:
            return self.metadata
        
        return {table: self.metadata[table] for table in relevant_tables if table in self.metadata}
    
    def _get_relevant_statistics(self, question: str) -> str:
        """Retorna estatísticas relevantes"""
        stats = []
        
        if "lento" in question.lower() or "otimizar" in question.lower():
            stats.append(f"Padrões lentos conhecidos:\n{json.dumps(self.query_statistics['slow_patterns'], indent=2)}")
        
        stats.append(f"Limites otimizados:\n{json.dumps(self.query_statistics['optimal_limits'], indent=2)}")
        
        return "\n\n".join(stats)


schema_retriever = MultiLayerSchemaRetriever()