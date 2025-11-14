from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from src.config.database import Base


class Cliente(Base):
    __tablename__ = 'clientes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    saldo = Column(Float, nullable=False, default=0.0)
    data_cadastro = Column(DateTime, default=datetime.utcnow)
    
    transacoes = relationship('Transacao', back_populates='cliente', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<Cliente(id={self.id}, nome='{self.nome}', saldo={self.saldo})>"


class Produto(Base):
    __tablename__ = 'produtos'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(100), nullable=False)
    categoria = Column(String(50), nullable=False)
    preco = Column(Float, nullable=False)
    estoque = Column(Integer, nullable=False, default=0)
    descricao = Column(Text)
    
    transacoes = relationship('Transacao', back_populates='produto')
    
    def __repr__(self):
        return f"<Produto(id={self.id}, nome='{self.nome}', preco={self.preco})>"


class Transacao(Base):
    __tablename__ = 'transacoes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    cliente_id = Column(Integer, ForeignKey('clientes.id', ondelete='CASCADE'), nullable=False)
    produto_id = Column(Integer, ForeignKey('produtos.id', ondelete='CASCADE'), nullable=False)
    quantidade = Column(Integer, nullable=False, default=1)
    valor_total = Column(Float, nullable=False)
    data_transacao = Column(DateTime, default=datetime.utcnow)
    
    cliente = relationship('Cliente', back_populates='transacoes')
    produto = relationship('Produto', back_populates='transacoes')
    
    def __repr__(self):
        return f"<Transacao(id={self.id}, cliente_id={self.cliente_id}, produto_id={self.produto_id}, valor={self.valor_total})>"