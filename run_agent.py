import logging
import sys
from sqlalchemy import text, create_engine

# URL correta baseada no teste
DATABASE_URL = "postgresql://sql_agent_user:secure_password@localhost/sql_agent_db"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)


class SQLAgent:
    def __init__(self):
        logger.info("🚀 Inicializando SQL Agent...")
        self.engine = create_engine(DATABASE_URL)
        self.test_connection()
    
    def test_connection(self):
        with self.engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM clientes"))
            count = result.scalar()
            logger.info(f"✓ Conexão estabelecida! Total de clientes: {count}")
    
    def execute_query(self, sql_query: str, description: str):
        print(f"\n{'='*80}")
        print(f"  {description}")
        print(f"{'='*80}\n")
        
        with self.engine.connect() as conn:
            result = conn.execute(text(sql_query))
            rows = result.fetchall()
            columns = result.keys()
            
            if rows:
                header = " | ".join([str(col).ljust(20)[:20] for col in columns])
                print(header)
                print("-" * 80)
                
                for row in rows:
                    row_data = " | ".join([str(val).ljust(20)[:20] for val in row])
                    print(row_data)
                
                print(f"\n✓ Total: {len(rows)} registro(s)")
            else:
                print("  Nenhum resultado encontrado.")


def main():
    print("\n" + "="*80)
    print("  🤖 SQL AGENT INTELIGENTE - DEMONSTRAÇÃO REAL COM POSTGRESQL")
    print("="*80 + "\n")
    
    agent = SQLAgent()
    
    consultas = [
        ('📋 CONSULTA 1: Listar todos os clientes',
         'SELECT nome, email, saldo FROM clientes ORDER BY nome'),
        
        ('📦 CONSULTA 2: Listar todos os produtos',
         'SELECT nome, categoria, preco, estoque FROM produtos ORDER BY categoria, nome'),
        
        ('💻 CONSULTA 3: Quais clientes compraram Notebook?',
         '''SELECT DISTINCT c.nome, c.email, t.valor_total
            FROM clientes c
            JOIN transacoes t ON c.id = t.cliente_id
            JOIN produtos p ON t.produto_id = p.id
            WHERE p.nome ILIKE '%notebook%'
            ORDER BY c.nome'''),
        
        ('💰 CONSULTA 4: Quanto cada cliente gastou no total?',
         '''SELECT c.nome, COALESCE(SUM(t.valor_total), 0) as total_gasto,
                   COUNT(t.id) as num_compras
            FROM clientes c
            LEFT JOIN transacoes t ON c.id = t.cliente_id
            GROUP BY c.id, c.nome
            ORDER BY total_gasto DESC'''),
        
        ('📱 CONSULTA 5: Quem tem saldo para comprar Smartphone?',
         '''SELECT c.nome, c.saldo, p.preco, (c.saldo - p.preco) as saldo_restante
            FROM clientes c
            CROSS JOIN produtos p
            WHERE c.saldo >= p.preco AND p.nome ILIKE '%smartphone%'
            ORDER BY c.saldo DESC'''),
        
        ('🏆 CONSULTA 6: Produtos mais vendidos',
         '''SELECT p.nome as produto, COUNT(t.id) as total_vendas,
                   SUM(t.valor_total) as receita_total
            FROM produtos p
            JOIN transacoes t ON p.id = t.produto_id
            GROUP BY p.id, p.nome
            ORDER BY total_vendas DESC'''),
        
        ('📊 CONSULTA 7: Histórico completo de transações',
         '''SELECT c.nome as cliente, p.nome as produto, t.quantidade,
                   t.valor_total, t.data_transacao
            FROM transacoes t
            JOIN clientes c ON t.cliente_id = c.id
            JOIN produtos p ON t.produto_id = p.id
            ORDER BY t.data_transacao DESC'''),
    ]
    
    for i, (desc, sql) in enumerate(consultas, 1):
        agent.execute_query(sql, desc)
        
        if i < len(consultas):
            input("\n⏎  Pressione ENTER para próxima consulta...\n")
    
    print("\n" + "="*80)
    print("  ✅ DEMONSTRAÇÃO CONCLUÍDA COM SUCESSO!")
    print("="*80)
    print("\n  🎉 Parabéns! O SQL Agent está funcionando perfeitamente!")
    print("  📊 Todas as 7 consultas foram executadas com sucesso!")
    print("  🔗 Conexão: PostgreSQL + SQLAlchemy + Python")
    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    main()
