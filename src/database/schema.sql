-- Criacao das tabelas com indices e constraints

CREATE TABLE IF NOT EXISTS clientes (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    saldo FLOAT NOT NULL DEFAULT 0.0,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT check_saldo_positivo CHECK (saldo >= 0)
);

CREATE TABLE IF NOT EXISTS produtos (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    categoria VARCHAR(50) NOT NULL,
    preco FLOAT NOT NULL,
    estoque INTEGER NOT NULL DEFAULT 0,
    descricao TEXT,
    CONSTRAINT check_preco_positivo CHECK (preco >= 0),
    CONSTRAINT check_estoque_positivo CHECK (estoque >= 0)
);

CREATE TABLE IF NOT EXISTS transacoes (
    id SERIAL PRIMARY KEY,
    cliente_id INTEGER NOT NULL,
    produto_id INTEGER NOT NULL,
    quantidade INTEGER NOT NULL DEFAULT 1,
    valor_total FLOAT NOT NULL,
    data_transacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_cliente FOREIGN KEY (cliente_id) REFERENCES clientes(id) ON DELETE CASCADE,
    CONSTRAINT fk_produto FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE CASCADE,
    CONSTRAINT check_quantidade_positiva CHECK (quantidade > 0),
    CONSTRAINT check_valor_positivo CHECK (valor_total >= 0)
);

CREATE INDEX IF NOT EXISTS idx_cliente_email ON clientes(email);
CREATE INDEX IF NOT EXISTS idx_transacoes_cliente ON transacoes(cliente_id);
CREATE INDEX IF NOT EXISTS idx_transacoes_produto ON transacoes(produto_id);
CREATE INDEX IF NOT EXISTS idx_transacoes_data ON transacoes(data_transacao);
CREATE INDEX IF NOT EXISTS idx_produtos_categoria ON produtos(categoria);