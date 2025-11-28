from typing import List, Dict, Optional
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain.docstore.document import Document
from src.config.settings import settings
from src.orchestration.mcp_context import MCPContext
from src.observability.tracer import tracer
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
                "count": 5,
                "size_mb": 1,
                "has_index": True,
                "indexed_columns": ["id", "email"],
                "date_range": "2020-2025"
            },
            "transacoes": {
                "count": 10,
                "size_mb": 2,
                "has_index": True,
                "indexed_columns": ["cliente_id", "produto_id", "data_transacao"],
                "date_range": "2020-2025"
            },
            "produtos": {
                "count": 6,
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
                "SELECT * FROM transacoes",
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
        """Documentos com descrições detalhadas - SCHEMA CORRETO"""
        documents = [
            Document(
                page_content="""
                Tabela: clientes
                Colunas:
                - id (INTEGER, PRIMARY KEY, INDEXED): Identificador único
                - nome (VARCHAR): Nome completo do cliente
                - email (VARCHAR, UNIQUE, INDEXED): Email único do cliente
                - created_at (TIMESTAMP): Data de cadastro
                
                Cardinalidade: 5 registros
                Índices: PRIMARY KEY (id), UNIQUE (email)
                Relacionamentos: 1:N com transacoes (via cliente_id)
                
                Queries otimizadas:
                - Busca por email: O(1) devido a índice UNIQUE
                - Busca por id: O(1) devido a PRIMARY KEY
                - Contagem total: SELECT COUNT(*) - muito rápido
                """,
                metadata={'table': 'clientes', 'layer': 'schema'}
            ),
            Document(
                page_content="""
                Tabela: produtos
                Colunas:
                - id (INTEGER, PRIMARY KEY, INDEXED): Identificador único
                - nome (VARCHAR): Nome do produto
                - preco (DECIMAL): Preço unitário do produto
                - categoria (VARCHAR): Categoria do produto
                
                Cardinalidade: 6 produtos
                Índices: PRIMARY KEY (id)
                Relacionamentos: 1:N com transacoes (via produto_id)
                
                Categorias existentes:
                - "Eletrônicos" (Notebook, Smartphone, Tablet, Monitor)
                - "Periféricos" (Teclado, Mouse)
                
                Queries otimizadas:
                - Filtro por categoria: Rápido
                - Ordenação por preco: DESC para mais caros, ASC para mais baratos
                - Top N produtos: adicione LIMIT N
                """,
                metadata={'table': 'produtos', 'layer': 'schema'}
            ),
            Document(
                page_content="""
                Tabela: transacoes (ATENÇÃO: Use nomes de colunas EXATOS!)
                Colunas CORRETAS:
                - id (INTEGER, PRIMARY KEY)
                - cliente_id (INTEGER, FK para clientes.id, INDEXED)
                - produto_id (INTEGER, FK para produtos.id, INDEXED)
                - quantidade (INTEGER): Quantidade comprada
                - valor_total (DECIMAL): Valor total da transação
                - data_transacao (TIMESTAMP): Data da compra
                
                ⚠️⚠️⚠️ CRÍTICO - NOMES DE COLUNAS ⚠️⚠️⚠️
                A coluna de valor se chama "valor_total" (NÃO "valor", NÃO "preco")
                SEMPRE use: transacoes.valor_total
                NUNCA use: transacoes.valor (esta coluna NÃO existe!)
                
                Cardinalidade: 10 registros
                Índices: PRIMARY KEY (id), INDEX (cliente_id), INDEX (produto_id)
                
                Relacionamentos:
                - N:1 com clientes (cliente_id → clientes.id)
                - N:1 com produtos (produto_id → produtos.id)
                
                ⚠️ BOAS PRÁTICAS:
                - SEMPRE use LIMIT para evitar resultados grandes
                - Para agregações: GROUP BY cliente_id ou produto_id
                - Para somas: SUM(valor_total) - não esqueça "valor_total"!
                
                Queries otimizadas:
                - Total gasto por cliente:
                  SELECT c.nome, SUM(t.valor_total) as total
                  FROM clientes c
                  JOIN transacoes t ON c.id = t.cliente_id
                  GROUP BY c.id, c.nome
                  
                - Clientes que compraram produto X:
                  SELECT DISTINCT c.nome
                  FROM clientes c
                  JOIN transacoes t ON c.id = t.cliente_id
                  JOIN produtos p ON t.produto_id = p.id
                  WHERE p.nome ILIKE '%produto%'
                """,
                metadata={'table': 'transacoes', 'layer': 'schema'}
            ),
            Document(
                page_content="""
                EXEMPLOS DE QUERIES CORRETAS - COPIE ESTES PADRÕES:
                
                1. Contar clientes:
                   SELECT COUNT(*) FROM clientes;
                
                2. Produtos mais caros (TOP 10):
                   SELECT nome, preco 
                   FROM produtos 
                   ORDER BY preco DESC 
                   LIMIT 10;
                
                3. Clientes que compraram notebook:
                   SELECT DISTINCT c.nome
                   FROM clientes c
                   JOIN transacoes t ON c.id = t.cliente_id
                   JOIN produtos p ON t.produto_id = p.id
                   WHERE p.nome ILIKE '%notebook%';
                
                4. Total gasto por cliente:
                   SELECT c.nome, SUM(t.valor_total) as total_gasto
                   FROM clientes c
                   JOIN transacoes t ON c.id = t.cliente_id
                   GROUP BY c.id, c.nome
                   ORDER BY total_gasto DESC;
                
                5. Transações por produto:
                   SELECT p.nome, COUNT(*) as num_vendas, SUM(t.valor_total) as receita
                   FROM produtos p
                   JOIN transacoes t ON p.id = t.produto_id
                   GROUP BY p.id, p.nome
                   ORDER BY receita DESC;
                
                ⚠️ LEMBRE-SE: A coluna é "valor_total", não "valor"!
                """,
                metadata={'type': 'examples', 'layer': 'patterns'}
            )
        ]
        return documents
    
    def retrieve(self, context: MCPContext) -> MCPContext:
        """Retrieve com contexto MCP"""
        with tracer.start_span("retrieve_schema", attributes={"user_id": context.user_id}):
            try:
                strategy = context.metadata.get('routing_strategy', 'full_pipeline')
                result = self.retrieve_relevant_schema(context.original_question, strategy)
                
                # Formata contexto completo
                schema_text = "=== SCHEMA DO BANCO DE DADOS ===\n\n"
                
                if result['metadata']:
                    schema_text += "METADADOS DAS TABELAS:\n"
                    schema_text += json.dumps(result['metadata'], indent=2)
                    schema_text += "\n\n"
                
                if result['schema']:
                    schema_text += "ESTRUTURA DAS TABELAS:\n"
                    schema_text += result['schema']
                    schema_text += "\n\n"
                
                if result['statistics']:
                    schema_text += "ESTATÍSTICAS E OTIMIZAÇÕES:\n"
                    schema_text += result['statistics']
                
                context.schema_context = schema_text
                context.metadata['schema_retrieval_strategy'] = strategy
                
                logger.info(f"Schema retrieved for user {context.user_id}")
                
            except Exception as e:
                error_msg = f"Schema retrieval failed: {str(e)}"
                logger.error(error_msg)
                context.add_error("schema_retriever", error_msg)
                tracer.log_error("schema_retriever", e)
        
        return context
    
    def retrieve_relevant_schema(self, question: str, strategy: str = "full") -> Dict:
        """Retrieve com estratégia adaptativa"""
        try:
            # LAYER 1: Sempre retorna metadados
            metadata_context = self._filter_metadata_by_question(question)
            
            # LAYER 2: Schema RAG (só se necessário)
            schema_context = ""
            if strategy in ["full_pipeline", "filtered_rag"]:
                docs = self.vectorstore.similarity_search(question, k=3)
                schema_context = "\n\n".join([doc.page_content for doc in docs])
            
            # LAYER 3: Estatísticas
            stats_context = ""
            if strategy in ["full_pipeline"]:
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
        """Filtra metadados relevantes"""
        question_lower = question.lower()
        
        relevant_tables = []
        if "cliente" in question_lower:
            relevant_tables.append("clientes")
        if "produto" in question_lower:
            relevant_tables.append("produtos")
        if "transacao" in question_lower or "compra" in question_lower or "gasto" in question_lower or "total" in question_lower:
            relevant_tables.append("transacoes")
        
        if not relevant_tables:
            return self.metadata
        
        return {table: self.metadata[table] for table in relevant_tables if table in self.metadata}
    
    def _get_relevant_statistics(self, question: str) -> str:
        """Retorna estatísticas relevantes"""
        stats = []
        stats.append(f"Limites otimizados por tabela:\n{json.dumps(self.query_statistics['optimal_limits'], indent=2)}")
        return "\n\n".join(stats)


schema_retriever = MultiLayerSchemaRetriever()
