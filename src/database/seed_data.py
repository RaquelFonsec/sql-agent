from src.database.models import Cliente, Produto, Transacao
from src.config.database import get_db_session
import logging

logger = logging.getLogger(__name__)


def seed_database():
    with get_db_session() as session:
        if session.query(Cliente).count() > 0:
            logger.info("Database already seeded, skipping...")
            return
        
        clientes = [
            Cliente(nome='João Silva', email='joao@email.com', saldo=5000.00),
            Cliente(nome='Maria Santos', email='maria@email.com', saldo=3000.00),
            Cliente(nome='Pedro Oliveira', email='pedro@email.com', saldo=7500.00),
            Cliente(nome='Ana Costa', email='ana@email.com', saldo=2000.00),
            Cliente(nome='Carlos Souza', email='carlos@email.com', saldo=4500.00),
        ]
        
        produtos = [
            Produto(nome='Notebook', categoria='Eletronicos', preco=3500.00, estoque=10, 
                   descricao='Notebook de alta performance'),
            Produto(nome='Smartphone', categoria='Eletronicos', preco=2000.00, estoque=15,
                   descricao='Smartphone com camera avancada'),
            Produto(nome='Tablet', categoria='Eletronicos', preco=1500.00, estoque=20,
                   descricao='Tablet para produtividade'),
            Produto(nome='Mouse', categoria='Perifericos', preco=50.00, estoque=50,
                   descricao='Mouse ergonomico'),
            Produto(nome='Teclado', categoria='Perifericos', preco=150.00, estoque=30,
                   descricao='Teclado mecanico'),
            Produto(nome='Monitor', categoria='Perifericos', preco=800.00, estoque=12,
                   descricao='Monitor 27 polegadas'),
        ]
        
        session.add_all(clientes)
        session.add_all(produtos)
        session.flush()
        
        transacoes = [
            Transacao(cliente_id=1, produto_id=1, quantidade=1, valor_total=3500.00),
            Transacao(cliente_id=1, produto_id=4, quantidade=2, valor_total=100.00),
            Transacao(cliente_id=2, produto_id=2, quantidade=1, valor_total=2000.00),
            Transacao(cliente_id=3, produto_id=1, quantidade=1, valor_total=3500.00),
            Transacao(cliente_id=3, produto_id=6, quantidade=2, valor_total=1600.00),
            Transacao(cliente_id=4, produto_id=3, quantidade=1, valor_total=1500.00),
            Transacao(cliente_id=5, produto_id=2, quantidade=1, valor_total=2000.00),
            Transacao(cliente_id=5, produto_id=5, quantidade=1, valor_total=150.00),
        ]
        
        session.add_all(transacoes)
        session.commit()
        
        logger.info("Database seeded successfully")