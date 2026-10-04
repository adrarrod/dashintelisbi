-- Esquema padrão de cada base de cliente (data/<cliente>.db).
-- Cada cliente tem seu próprio arquivo SQLite; tabelas extras podem ser
-- adicionadas por cliente conforme a necessidade, sem afetar os demais.

CREATE TABLE IF NOT EXISTS empresa (
    chave TEXT PRIMARY KEY,
    valor TEXT
);

CREATE TABLE IF NOT EXISTS clientes (
    id            INTEGER PRIMARY KEY,
    nome          TEXT NOT NULL,
    documento     TEXT,
    cidade        TEXT,
    uf            TEXT,
    segmento      TEXT,
    data_cadastro DATE,
    ativo         INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS fornecedores (
    id                 INTEGER PRIMARY KEY,
    nome               TEXT NOT NULL,
    documento          TEXT,
    cidade             TEXT,
    uf                 TEXT,
    categoria          TEXT,
    prazo_entrega_dias INTEGER,
    avaliacao          REAL
);

CREATE TABLE IF NOT EXISTS produtos (
    id             INTEGER PRIMARY KEY,
    nome           TEXT NOT NULL,
    categoria      TEXT,
    preco_unitario REAL NOT NULL,
    custo_unitario REAL NOT NULL,
    fornecedor_id  INTEGER REFERENCES fornecedores(id)
);

CREATE TABLE IF NOT EXISTS vendas (
    id             INTEGER PRIMARY KEY,
    data           DATE NOT NULL,
    cliente_id     INTEGER NOT NULL REFERENCES clientes(id),
    produto_id     INTEGER NOT NULL REFERENCES produtos(id),
    quantidade     INTEGER NOT NULL,
    valor_unitario REAL NOT NULL,
    desconto       REAL NOT NULL DEFAULT 0,
    valor_total    REAL NOT NULL,
    custo_total    REAL NOT NULL,
    vendedor       TEXT,
    canal          TEXT,
    status         TEXT NOT NULL DEFAULT 'faturada' -- faturada | cancelada
);
CREATE INDEX IF NOT EXISTS ix_vendas_data ON vendas(data);

CREATE TABLE IF NOT EXISTS compras (
    id            INTEGER PRIMARY KEY,
    data          DATE NOT NULL,
    fornecedor_id INTEGER NOT NULL REFERENCES fornecedores(id),
    valor         REAL NOT NULL,
    prazo_dias    INTEGER,
    entregue_no_prazo INTEGER NOT NULL DEFAULT 1,
    status        TEXT NOT NULL DEFAULT 'recebida' -- recebida | pendente
);
CREATE INDEX IF NOT EXISTS ix_compras_data ON compras(data);

-- Orçamento mensal: previsto x realizado por categoria (receita ou despesa).
CREATE TABLE IF NOT EXISTS orcamento (
    id              INTEGER PRIMARY KEY,
    ano             INTEGER NOT NULL,
    mes             INTEGER NOT NULL,
    tipo            TEXT NOT NULL CHECK (tipo IN ('receita', 'despesa')),
    categoria       TEXT NOT NULL,
    valor_previsto  REAL NOT NULL,
    valor_realizado REAL,
    UNIQUE (ano, mes, tipo, categoria)
);
