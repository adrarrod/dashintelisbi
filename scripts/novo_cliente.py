"""Cria a base SQLite de um cliente a partir do esquema padrão.

Uso:
    python scripts/novo_cliente.py <slug> --nome "Nome da Empresa" [--exemplo]
    python scripts/novo_cliente.py --demo        # cria duas bases de exemplo

A base fica em data/<slug>.db. Com --exemplo, ela é preenchida com dados
fictícios para visualizar o dashboard.
"""
import argparse
import random
import re
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATA_DIR = RAIZ / "data"
SCHEMA = RAIZ / "db" / "schema.sql"
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


def criar_base(slug, nome, sobrescrever=False):
    if not SLUG_RE.match(slug):
        sys.exit(f"Slug inválido: {slug!r} (use letras minúsculas, números, - ou _)")
    DATA_DIR.mkdir(exist_ok=True)
    caminho = DATA_DIR / f"{slug}.db"
    if caminho.exists():
        if not sobrescrever:
            sys.exit(f"{caminho} já existe (use --sobrescrever para recriar)")
        caminho.unlink()
    con = sqlite3.connect(caminho)
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    con.execute("INSERT OR REPLACE INTO empresa VALUES ('nome', ?)", (nome,))
    con.commit()
    return con, caminho


CIDADES = [("São Paulo", "SP"), ("Campinas", "SP"), ("Rio de Janeiro", "RJ"),
           ("Belo Horizonte", "MG"), ("Curitiba", "PR"), ("Porto Alegre", "RS"),
           ("Salvador", "BA"), ("Recife", "PE"), ("Goiânia", "GO"), ("Florianópolis", "SC")]
SEGMENTOS = ["Varejo", "Indústria", "Serviços", "Governo", "Saúde"]
NOMES = ["Alfa", "Beta", "Delta", "Ômega", "Prisma", "Horizonte", "Atlas", "Vértice",
         "Nova", "Sigma", "Áurea", "Boreal", "Cristal", "Duna", "Estrela", "Fênix",
         "Granito", "Íris", "Jade", "Lótus", "Marés", "Norte", "Orion", "Pampa"]
SUFIXOS = ["Comércio", "Ltda", "S.A.", "Distribuidora", "Serviços", "Indústria"]
VENDEDORES = ["Ana Souza", "Bruno Lima", "Carla Dias", "Diego Rocha", "Elaine Melo"]
CANAIS = ["Loja", "E-commerce", "Representante", "Televendas"]

PERFIS = {
    "tecnologia": {
        "categorias": {
            "Notebooks": (3200, 6500), "Monitores": (700, 1900), "Periféricos": (60, 450),
            "Software": (300, 2500), "Serviços": (500, 4000),
        },
        "forn_cat": ["Hardware", "Software", "Logística", "Serviços"],
    },
    "alimentos": {
        "categorias": {
            "Padaria": (5, 40), "Laticínios": (6, 35), "Bebidas": (4, 60),
            "Mercearia": (3, 30), "Congelados": (12, 70),
        },
        "forn_cat": ["Matéria-prima", "Embalagens", "Logística", "Manutenção"],
    },
}
DESPESAS = ["Pessoal", "Marketing", "Infraestrutura", "Logística", "Administrativo"]


def nome_empresa(rng):
    return f"{rng.choice(NOMES)} {rng.choice(NOMES)} {rng.choice(SUFIXOS)}"


def doc(rng):
    d = [rng.randint(0, 9) for _ in range(14)]
    return "{}{}.{}{}{}.{}{}{}/{}{}{}{}-{}{}".format(*d)


def preencher_exemplo(con, perfil="tecnologia", semente=42, meses=24):
    rng = random.Random(semente)
    cfg = PERFIS[perfil]
    ultimo_dia = date.today()
    hoje = ultimo_dia.replace(day=1)
    inicio = (hoje - timedelta(days=meses * 31)).replace(day=1)

    # Fornecedores
    fornecedores = []
    for i in range(1, 13):
        cid, uf = rng.choice(CIDADES)
        fornecedores.append((i, nome_empresa(rng), doc(rng), cid, uf, rng.choice(cfg["forn_cat"]),
                             rng.randint(2, 30), round(rng.uniform(2.5, 5.0), 1)))
    con.executemany("INSERT INTO fornecedores VALUES (?,?,?,?,?,?,?,?)", fornecedores)

    # Produtos
    produtos = []
    pid = 1
    for cat, (pmin, pmax) in cfg["categorias"].items():
        for n in range(1, 6):
            preco = round(rng.uniform(pmin, pmax), 2)
            custo = round(preco * rng.uniform(0.45, 0.8), 2)
            produtos.append((pid, f"{cat} {chr(64 + n)}{rng.randint(100, 999)}", cat, preco, custo,
                             rng.randint(1, len(fornecedores))))
            pid += 1
    con.executemany("INSERT INTO produtos VALUES (?,?,?,?,?,?)", produtos)

    # Clientes
    clientes = []
    for i in range(1, 121):
        cid, uf = rng.choice(CIDADES)
        cadastro = inicio + timedelta(days=rng.randint(-365, meses * 30))
        clientes.append((i, nome_empresa(rng), doc(rng), cid, uf, rng.choice(SEGMENTOS),
                         cadastro.isoformat(), 1 if rng.random() > 0.12 else 0))
    con.executemany("INSERT INTO clientes VALUES (?,?,?,?,?,?,?,?)", clientes)
    # clientes "grandes" compram mais (curva ABC realista)
    pesos_cli = [rng.paretovariate(1.3) for _ in clientes]

    # Vendas
    vendas = []
    vid = 1
    d = inicio
    while d <= ultimo_dia:
        sazonal = 1 + 0.25 * (d.month in (11, 12)) - 0.15 * (d.month in (1, 2))
        crescimento = 1 + (d - inicio).days / 365 * 0.18
        for _ in range(rng.randint(2, 7)):
            if rng.random() > 0.7 * sazonal * crescimento:
                continue
            cli = rng.choices(clientes, weights=pesos_cli)[0]
            prod = rng.choice(produtos)
            qtd = rng.randint(1, 12)
            desc = rng.choice([0, 0, 0, 0.05, 0.1])
            total = round(qtd * prod[3] * (1 - desc), 2)
            vendas.append((vid, d.isoformat(), cli[0], prod[0], qtd, prod[3], desc, total,
                           round(qtd * prod[4], 2), rng.choice(VENDEDORES), rng.choice(CANAIS),
                           "cancelada" if rng.random() < 0.04 else "faturada"))
            vid += 1
        d += timedelta(days=1)
    con.executemany("INSERT INTO vendas VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", vendas)

    # Compras
    compras = []
    cid_ = 1
    d = inicio
    while d <= ultimo_dia:
        if rng.random() < 0.35:
            f = rng.choice(fornecedores)
            no_prazo = 1 if rng.random() < (f[7] / 5.2) else 0
            compras.append((cid_, d.isoformat(), f[0], round(rng.uniform(800, 25000), 2),
                            f[6], no_prazo, "pendente" if d > hoje - timedelta(days=20) else "recebida"))
            cid_ += 1
        d += timedelta(days=1)
    con.executemany("INSERT INTO compras VALUES (?,?,?,?,?,?,?)", compras)

    # Orçamento: previsto x realizado
    receita_mes = {}
    for v in vendas:
        if v[11] != "faturada":
            continue
        chave = (v[1][:7], next(p[2] for p in produtos if p[0] == v[3]))
        receita_mes[chave] = receita_mes.get(chave, 0) + v[7]
    orc = []
    oid = 1
    d = inicio
    while d <= hoje:
        mes_txt = d.strftime("%Y-%m")
        corrente = d == hoje
        for cat in cfg["categorias"]:
            real = round(receita_mes.get((mes_txt, cat), 0), 2)
            prev = round(real * rng.uniform(0.85, 1.2) or rng.uniform(1000, 5000), 2)
            orc.append((oid, d.year, d.month, "receita", cat, prev, None if corrente else real))
            oid += 1
        total_rec = sum(receita_mes.get((mes_txt, c), 0) for c in cfg["categorias"])
        for cat, frac in zip(DESPESAS, (0.28, 0.08, 0.1, 0.06, 0.07)):
            prev = round(total_rec * frac * rng.uniform(0.9, 1.1) + 500, 2)
            real = round(prev * rng.uniform(0.85, 1.18), 2)
            orc.append((oid, d.year, d.month, "despesa", cat, prev, None if corrente else real))
            oid += 1
        d = (d + timedelta(days=32)).replace(day=1)
    con.executemany("INSERT INTO orcamento VALUES (?,?,?,?,?,?,?)", orc)
    con.commit()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("slug", nargs="?", help="identificador do cliente (nome do arquivo .db)")
    ap.add_argument("--nome", help="nome de exibição do cliente")
    ap.add_argument("--exemplo", action="store_true", help="preenche com dados fictícios")
    ap.add_argument("--perfil", choices=sorted(PERFIS), default="tecnologia")
    ap.add_argument("--sobrescrever", action="store_true")
    ap.add_argument("--demo", action="store_true", help="cria as bases de exemplo 'techsul' e 'padaria-central'")
    a = ap.parse_args()

    if a.demo:
        for slug, nome, perfil, sem in [("techsul", "TechSul Informática", "tecnologia", 7),
                                        ("padaria-central", "Padaria Central", "alimentos", 11)]:
            con, caminho = criar_base(slug, nome, sobrescrever=True)
            preencher_exemplo(con, perfil, sem)
            con.close()
            print(f"Base de exemplo criada: {caminho}")
        return
    if not a.slug:
        ap.error("informe o slug do cliente ou use --demo")
    con, caminho = criar_base(a.slug, a.nome or a.slug, a.sobrescrever)
    if a.exemplo:
        preencher_exemplo(con, a.perfil)
    con.close()
    print(f"Base criada: {caminho}")


if __name__ == "__main__":
    main()
