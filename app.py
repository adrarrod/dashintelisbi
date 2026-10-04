"""DashIntelisBI: dashboard no estilo AdminLTE com uma base SQLite por cliente.

Cada cliente é um arquivo data/<slug>.db com o esquema de db/schema.sql.
As páginas HTML são servidas por Flask e buscam os dados em /api/<slug>/...
"""
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path

from flask import Flask, abort, jsonify, redirect, render_template, request, url_for

RAIZ = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DASH_DATA_DIR", RAIZ / "data"))
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
LIMITE_CONSULTA = 1000

PAGINAS = [
    ("visao-geral", "Visão Geral", "fas fa-tachometer-alt"),
    ("vendas", "Vendas", "fas fa-shopping-cart"),
    ("orcamento", "Orçamento", "fas fa-wallet"),
    ("clientes", "Clientes", "fas fa-users"),
    ("fornecedores", "Fornecedores", "fas fa-truck"),
    ("analise", "Análise de Dados", "fas fa-chart-line"),
]
PAGINAS_SLUGS = {p[0] for p in PAGINAS}

# Arquivos estáticos ficam em public/static: a Vercel serve public/** direto pela CDN,
# e localmente o Flask serve a mesma pasta em /static.
app = Flask(__name__, static_folder="public/static", static_url_path="/static")


# --------------------------------------------------------------------------- bases

def listar_clientes():
    clientes = []
    for arq in sorted(DATA_DIR.glob("*.db")):
        slug = arq.stem
        if not SLUG_RE.match(slug):
            continue
        nome = slug
        try:
            with sqlite3.connect(f"file:{arq}?mode=ro", uri=True) as con:
                row = con.execute("SELECT valor FROM empresa WHERE chave = 'nome'").fetchone()
                if row and row[0]:
                    nome = row[0]
        except sqlite3.Error:
            pass
        clientes.append({"slug": slug, "nome": nome})
    return clientes


def caminho_base(slug):
    if not SLUG_RE.match(slug):
        abort(404)
    caminho = DATA_DIR / f"{slug}.db"
    if not caminho.is_file():
        abort(404)
    return caminho


def pode_editar(slug):
    """Cadastro só é liberado quando a base pode ser gravada (no seu computador).

    Na Vercel o disco é somente leitura; DASH_SOMENTE_LEITURA=1 também bloqueia.
    """
    if os.environ.get("VERCEL") or os.environ.get("DASH_SOMENTE_LEITURA") == "1":
        return False
    caminho = caminho_base(slug)
    return os.access(caminho, os.W_OK) and os.access(caminho.parent, os.W_OK)


@contextmanager
def conectar(slug, escrita=False):
    """Abre a base do cliente (somente leitura por padrão) e fecha ao final."""
    caminho = caminho_base(slug)
    con = sqlite3.connect(f"file:{caminho}?mode={'rw' if escrita else 'ro'}", uri=True)
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()


def linhas(con, sql, params=()):
    return [dict(r) for r in con.execute(sql, params).fetchall()]


def valor(con, sql, params=()):
    row = con.execute(sql, params).fetchone()
    return row[0] if row else None


def periodo(con):
    """Lê ?inicio=&fim= (AAAA-MM-DD); padrão: últimos 12 meses com dados."""
    data_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    inicio = request.args.get("inicio", "")
    fim = request.args.get("fim", "")
    ultima = valor(con, "SELECT MAX(data) FROM vendas") or date.today().isoformat()
    if not data_re.match(fim):
        fim = ultima
    if not data_re.match(inicio):
        a, m = int(fim[:4]) - 1, int(fim[5:7]) + 1
        if m > 12:
            a, m = a + 1, 1
        inicio = f"{a:04d}-{m:02d}-01"
    return inicio, fim


# --------------------------------------------------------------------------- páginas

@app.context_processor
def contexto_global():
    return {"paginas": PAGINAS}


@app.route("/")
def inicio():
    clientes = listar_clientes()
    if not clientes:
        return render_template("sem_clientes.html", data_dir=DATA_DIR)
    return redirect(url_for("pagina", cliente=clientes[0]["slug"], pagina="visao-geral"))


@app.route("/c/<cliente>/")
@app.route("/c/<cliente>/<pagina>")
def pagina(cliente, pagina="visao-geral"):
    if pagina not in PAGINAS_SLUGS:
        abort(404)
    caminho_base(cliente)
    clientes = listar_clientes()
    atual = next((c for c in clientes if c["slug"] == cliente), {"slug": cliente, "nome": cliente})
    titulo = next(p[1] for p in PAGINAS if p[0] == pagina)
    return render_template(f"{pagina.replace('-', '_')}.html", clientes=clientes, cliente=atual,
                           pagina=pagina, titulo=titulo, pode_editar=pode_editar(cliente),
                           ufs=UFS)


# --------------------------------------------------------------------------- API

FATURADA = "status = 'faturada'"


def kpis_vendas(con, inicio, fim):
    r = con.execute(
        f"""SELECT COALESCE(SUM(valor_total),0) faturamento, COUNT(*) pedidos,
                   COALESCE(SUM(valor_total - custo_total),0) margem,
                   COUNT(DISTINCT cliente_id) clientes
            FROM vendas WHERE {FATURADA} AND data BETWEEN ? AND ?""", (inicio, fim)).fetchone()
    d = dict(r)
    d["ticket_medio"] = d["faturamento"] / d["pedidos"] if d["pedidos"] else 0
    d["margem_pct"] = d["margem"] / d["faturamento"] * 100 if d["faturamento"] else 0
    return d


def mensal_vendas(con, inicio, fim):
    return linhas(con, f"""SELECT substr(data,1,7) mes, SUM(valor_total) faturamento,
                                  SUM(valor_total - custo_total) margem, COUNT(*) pedidos
                           FROM vendas WHERE {FATURADA} AND data BETWEEN ? AND ?
                           GROUP BY mes ORDER BY mes""", (inicio, fim))


@app.route("/api/clientes-disponiveis")
def api_clientes_disponiveis():
    return jsonify(listar_clientes())


@app.route("/api/<cliente>/visao-geral")
def api_visao_geral(cliente):
    with conectar(cliente) as con:
        inicio, fim = periodo(con)
        ano = int(fim[:4])
        orc = dict(con.execute(
            """SELECT SUM(CASE WHEN tipo='receita' THEN valor_previsto END) receita_prevista,
                      SUM(CASE WHEN tipo='receita' THEN valor_realizado END) receita_realizada,
                      SUM(CASE WHEN tipo='despesa' THEN valor_previsto END) despesa_prevista,
                      SUM(CASE WHEN tipo='despesa' THEN valor_realizado END) despesa_realizada
               FROM orcamento WHERE ano = ? AND valor_realizado IS NOT NULL""", (ano,)).fetchone())
        return jsonify({
            "periodo": {"inicio": inicio, "fim": fim},
            "kpis": kpis_vendas(con, inicio, fim),
            "total_clientes": valor(con, "SELECT COUNT(*) FROM clientes WHERE ativo = 1"),
            "total_fornecedores": valor(con, "SELECT COUNT(*) FROM fornecedores"),
            "orcamento": {"ano": ano, **orc},
            "mensal": mensal_vendas(con, inicio, fim),
            "por_categoria": linhas(con, f"""
                SELECT p.categoria, SUM(v.valor_total) faturamento
                FROM vendas v JOIN produtos p ON p.id = v.produto_id
                WHERE v.{FATURADA} AND v.data BETWEEN ? AND ?
                GROUP BY p.categoria ORDER BY faturamento DESC""", (inicio, fim)),
            "ultimas_vendas": linhas(con, """
                SELECT v.data, c.nome cliente, p.nome produto, v.valor_total, v.status
                FROM vendas v JOIN clientes c ON c.id = v.cliente_id JOIN produtos p ON p.id = v.produto_id
                WHERE v.data BETWEEN ? AND ? ORDER BY v.data DESC, v.id DESC LIMIT 8""", (inicio, fim)),
        })


@app.route("/api/<cliente>/vendas")
def api_vendas(cliente):
    with conectar(cliente) as con:
        inicio, fim = periodo(con)
        p = (inicio, fim)
        return jsonify({
            "periodo": {"inicio": inicio, "fim": fim},
            "kpis": kpis_vendas(con, inicio, fim),
            "canceladas": valor(con, "SELECT COUNT(*) FROM vendas WHERE status='cancelada' AND data BETWEEN ? AND ?", p),
            "mensal": mensal_vendas(con, inicio, fim),
            "por_canal": linhas(con, f"""SELECT canal rotulo, SUM(valor_total) valor FROM vendas
                WHERE {FATURADA} AND data BETWEEN ? AND ? GROUP BY canal ORDER BY valor DESC""", p),
            "por_vendedor": linhas(con, f"""SELECT vendedor rotulo, SUM(valor_total) valor, COUNT(*) pedidos
                FROM vendas WHERE {FATURADA} AND data BETWEEN ? AND ? GROUP BY vendedor ORDER BY valor DESC""", p),
            "top_produtos": linhas(con, f"""SELECT p.nome produto, p.categoria, SUM(v.quantidade) quantidade,
                       SUM(v.valor_total) faturamento
                FROM vendas v JOIN produtos p ON p.id = v.produto_id
                WHERE v.{FATURADA} AND v.data BETWEEN ? AND ?
                GROUP BY p.id ORDER BY faturamento DESC LIMIT 10""", p),
        })


@app.route("/api/<cliente>/orcamento")
def api_orcamento(cliente):
    with conectar(cliente) as con:
        anos = [r["ano"] for r in linhas(con, "SELECT DISTINCT ano FROM orcamento ORDER BY ano DESC")]
        try:
            ano = int(request.args.get("ano", anos[0] if anos else date.today().year))
        except ValueError:
            ano = anos[0] if anos else date.today().year
        mensal = linhas(con, """
            SELECT mes, tipo, SUM(valor_previsto) previsto, SUM(valor_realizado) realizado
            FROM orcamento WHERE ano = ? GROUP BY mes, tipo ORDER BY mes""", (ano,))
        categorias = linhas(con, """
            SELECT tipo, categoria, SUM(valor_previsto) previsto, SUM(valor_realizado) realizado,
                   SUM(CASE WHEN valor_realizado IS NOT NULL THEN valor_previsto END) previsto_ate_hoje
            FROM orcamento WHERE ano = ? GROUP BY tipo, categoria ORDER BY tipo DESC, previsto DESC""", (ano,))
        return jsonify({"ano": ano, "anos": anos, "mensal": mensal, "categorias": categorias})


@app.route("/api/<cliente>/clientes")
def api_clientes(cliente):
    with conectar(cliente) as con:
        inicio, fim = periodo(con)
        p = (inicio, fim)
        return jsonify({
            "periodo": {"inicio": inicio, "fim": fim},
            "total": valor(con, "SELECT COUNT(*) FROM clientes"),
            "ativos": valor(con, "SELECT COUNT(*) FROM clientes WHERE ativo = 1"),
            "novos": valor(con, "SELECT COUNT(*) FROM clientes WHERE data_cadastro BETWEEN ? AND ?", p),
            "compradores": valor(con, f"SELECT COUNT(DISTINCT cliente_id) FROM vendas WHERE {FATURADA} AND data BETWEEN ? AND ?", p),
            "por_segmento": linhas(con, f"""SELECT c.segmento rotulo, SUM(v.valor_total) valor
                FROM vendas v JOIN clientes c ON c.id = v.cliente_id
                WHERE v.{FATURADA} AND v.data BETWEEN ? AND ? GROUP BY c.segmento ORDER BY valor DESC""", p),
            "por_uf": linhas(con, """SELECT uf rotulo, COUNT(*) valor FROM clientes WHERE ativo = 1
                GROUP BY uf ORDER BY valor DESC"""),
            "novos_por_mes": linhas(con, """SELECT substr(data_cadastro,1,7) mes, COUNT(*) novos
                FROM clientes WHERE data_cadastro BETWEEN ? AND ? GROUP BY mes ORDER BY mes""", p),
            "ranking": linhas(con, f"""SELECT c.nome, c.cidade, c.uf, c.segmento, COUNT(v.id) pedidos,
                       SUM(v.valor_total) faturamento, MAX(v.data) ultima_compra
                FROM clientes c JOIN vendas v ON v.cliente_id = c.id
                WHERE v.{FATURADA} AND v.data BETWEEN ? AND ?
                GROUP BY c.id ORDER BY faturamento DESC LIMIT 15""", p),
        })


@app.route("/api/<cliente>/fornecedores")
def api_fornecedores(cliente):
    with conectar(cliente) as con:
        inicio, fim = periodo(con)
        p = (inicio, fim)
        return jsonify({
            "periodo": {"inicio": inicio, "fim": fim},
            "total": valor(con, "SELECT COUNT(*) FROM fornecedores"),
            "kpis": dict(con.execute("""SELECT COALESCE(SUM(valor),0) total_compras, COUNT(*) pedidos,
                       COALESCE(AVG(entregue_no_prazo) * 100, 0) pct_no_prazo,
                       SUM(status = 'pendente') pendentes
                FROM compras WHERE data BETWEEN ? AND ?""", p).fetchone()),
            "mensal": linhas(con, """SELECT substr(data,1,7) mes, SUM(valor) valor FROM compras
                WHERE data BETWEEN ? AND ? GROUP BY mes ORDER BY mes""", p),
            "por_categoria": linhas(con, """SELECT f.categoria rotulo, SUM(c.valor) valor
                FROM compras c JOIN fornecedores f ON f.id = c.fornecedor_id
                WHERE c.data BETWEEN ? AND ? GROUP BY f.categoria ORDER BY valor DESC""", p),
            "ranking": linhas(con, """SELECT f.nome, f.categoria, f.cidade, f.uf, f.avaliacao,
                       f.prazo_entrega_dias, COUNT(c.id) pedidos, COALESCE(SUM(c.valor),0) total,
                       AVG(c.entregue_no_prazo) * 100 pct_no_prazo
                FROM fornecedores f LEFT JOIN compras c ON c.fornecedor_id = f.id AND c.data BETWEEN ? AND ?
                GROUP BY f.id ORDER BY total DESC""", p),
        })


@app.route("/api/<cliente>/analise")
def api_analise(cliente):
    with conectar(cliente) as con:
        inicio, fim = periodo(con)
        p = (inicio, fim)
        por_cliente = linhas(con, f"""SELECT c.nome, SUM(v.valor_total) faturamento
            FROM vendas v JOIN clientes c ON c.id = v.cliente_id
            WHERE v.{FATURADA} AND v.data BETWEEN ? AND ? GROUP BY c.id ORDER BY faturamento DESC""", p)
        total = sum(r["faturamento"] for r in por_cliente) or 1
        acumulado = 0
        abc = {"A": {"clientes": 0, "faturamento": 0}, "B": {"clientes": 0, "faturamento": 0},
               "C": {"clientes": 0, "faturamento": 0}}
        curva = []
        for i, r in enumerate(por_cliente, 1):
            classe = "A" if acumulado / total < 0.8 else "B" if acumulado / total < 0.95 else "C"
            acumulado += r["faturamento"]
            abc[classe]["clientes"] += 1
            abc[classe]["faturamento"] += r["faturamento"]
            curva.append({"posicao": i, "pct_clientes": i / len(por_cliente) * 100,
                          "pct_acumulado": acumulado / total * 100})
        return jsonify({
            "periodo": {"inicio": inicio, "fim": fim},
            "abc": abc,
            "curva_abc": curva,
            "margem_categoria": linhas(con, f"""SELECT p.categoria rotulo,
                    SUM(v.valor_total - v.custo_total) / SUM(v.valor_total) * 100 valor
                FROM vendas v JOIN produtos p ON p.id = v.produto_id
                WHERE v.{FATURADA} AND v.data BETWEEN ? AND ? GROUP BY p.categoria ORDER BY valor DESC""", p),
            "dia_semana": linhas(con, f"""SELECT CAST(strftime('%w', data) AS INTEGER) dia,
                    SUM(valor_total) / COUNT(DISTINCT data) valor
                FROM vendas WHERE {FATURADA} AND data BETWEEN ? AND ? GROUP BY dia ORDER BY dia""", p),
            "ticket_mensal": linhas(con, f"""SELECT substr(data,1,7) mes, AVG(valor_total) valor
                FROM vendas WHERE {FATURADA} AND data BETWEEN ? AND ? GROUP BY mes ORDER BY mes""", p),
            "desconto": linhas(con, f"""SELECT CAST(ROUND(desconto * 100) AS INTEGER) desconto, COUNT(*) pedidos,
                    SUM(valor_total) faturamento,
                    SUM(valor_total - custo_total) / SUM(valor_total) * 100 margem_pct
                FROM vendas WHERE {FATURADA} AND data BETWEEN ? AND ? GROUP BY 1 ORDER BY 1""", p),
            "tabelas": [r["name"] for r in linhas(con, """SELECT name FROM sqlite_master
                WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY name""")],
        })


@app.route("/api/<cliente>/consulta", methods=["POST"])
def api_consulta(cliente):
    """Consulta SQL livre, somente leitura (a conexão é aberta em modo ro)."""
    sql = ((request.get_json(silent=True) or {}).get("sql") or "").strip().rstrip(";").strip()
    if not sql:
        return jsonify({"erro": "Informe uma consulta."}), 400
    if not re.match(r"^(select|with)\b", sql, re.I) or ";" in sql:
        return jsonify({"erro": "Apenas uma instrução SELECT (ou WITH ... SELECT) é permitida."}), 400
    try:
        with conectar(cliente) as con:
            con.execute("PRAGMA query_only = ON")
            cur = con.execute(sql)
            colunas = [d[0] for d in cur.description or []]
            dados = [list(r) for r in cur.fetchmany(LIMITE_CONSULTA + 1)]
    except sqlite3.Error as e:
        return jsonify({"erro": str(e)}), 400
    return jsonify({"colunas": colunas, "linhas": dados[:LIMITE_CONSULTA],
                    "truncado": len(dados) > LIMITE_CONSULTA})


# --------------------------------------------------------------------------- cadastro de clientes

UFS = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE",
       "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"]
POR_PAGINA = 20


def formatar_documento(doc):
    """Aceita CPF (11 dígitos) ou CNPJ (14 dígitos), com ou sem máscara."""
    d = re.sub(r"\D", "", doc or "")
    if not d:
        return None
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    raise ValueError("Documento deve ser um CPF (11 dígitos) ou CNPJ (14 dígitos).")


def validar_cliente(dados):
    erros = {}
    nome = (dados.get("nome") or "").strip()
    if not nome:
        erros["nome"] = "Informe o nome."
    elif len(nome) > 120:
        erros["nome"] = "Máximo de 120 caracteres."
    try:
        documento = formatar_documento(dados.get("documento"))
    except ValueError as e:
        erros["documento"] = str(e)
        documento = None
    uf = (dados.get("uf") or "").strip().upper() or None
    if uf and uf not in UFS:
        erros["uf"] = "UF inválida."
    cidade = (dados.get("cidade") or "").strip()[:80] or None
    segmento = (dados.get("segmento") or "").strip()[:40] or None
    ativo = 0 if str(dados.get("ativo", "1")).lower() in ("0", "false", "off", "") else 1
    return erros, {"nome": nome, "documento": documento, "cidade": cidade, "uf": uf,
                   "segmento": segmento, "ativo": ativo}


@app.route("/api/<cliente>/clientes/lista")
def api_clientes_lista(cliente):
    """Consulta paginada de clientes com filtros por texto, segmento, UF e situação."""
    q = request.args.get("q", "").strip()
    filtros, params = [], []
    if q:
        digitos = re.sub(r"\D", "", q)
        cond = "(c.nome LIKE ? OR c.cidade LIKE ?"
        params += [f"%{q}%", f"%{q}%"]
        if digitos:
            cond += " OR REPLACE(REPLACE(REPLACE(c.documento,'.',''),'/',''),'-','') LIKE ?"
            params.append(f"%{digitos}%")
        filtros.append(cond + ")")
    for campo in ("segmento", "uf"):
        if request.args.get(campo):
            filtros.append(f"c.{campo} = ?")
            params.append(request.args[campo])
    if request.args.get("ativo") in ("0", "1"):
        filtros.append("c.ativo = ?")
        params.append(int(request.args["ativo"]))
    where = ("WHERE " + " AND ".join(filtros)) if filtros else ""
    try:
        pagina = max(1, int(request.args.get("pagina", 1)))
    except ValueError:
        pagina = 1
    with conectar(cliente) as con:
        total = valor(con, f"SELECT COUNT(*) FROM clientes c {where}", params)
        registros = linhas(con, f"""
            SELECT c.*, COALESCE(v.faturamento, 0) faturamento, v.ultima_compra
            FROM clientes c
            LEFT JOIN (SELECT cliente_id, SUM(valor_total) faturamento, MAX(data) ultima_compra
                       FROM vendas WHERE {FATURADA} GROUP BY cliente_id) v ON v.cliente_id = c.id
            {where} ORDER BY c.nome COLLATE NOCASE LIMIT ? OFFSET ?""",
            params + [POR_PAGINA, (pagina - 1) * POR_PAGINA])
        segmentos = [r["segmento"] for r in linhas(con, """SELECT DISTINCT segmento FROM clientes
            WHERE segmento IS NOT NULL AND segmento <> '' ORDER BY segmento""")]
    return jsonify({"total": total, "pagina": pagina, "por_pagina": POR_PAGINA,
                    "registros": registros, "segmentos": segmentos})


@app.route("/api/<cliente>/clientes/<int:cid>")
def api_cliente_detalhe(cliente, cid):
    with conectar(cliente) as con:
        row = con.execute("SELECT * FROM clientes WHERE id = ?", (cid,)).fetchone()
        if not row:
            abort(404)
        resumo = dict(con.execute(f"""SELECT COUNT(*) pedidos, COALESCE(SUM(valor_total),0) faturamento,
                MIN(data) primeira_compra, MAX(data) ultima_compra
            FROM vendas WHERE {FATURADA} AND cliente_id = ?""", (cid,)).fetchone())
        compras = linhas(con, """SELECT v.data, p.nome produto, v.quantidade, v.valor_total, v.status
            FROM vendas v JOIN produtos p ON p.id = v.produto_id
            WHERE v.cliente_id = ? ORDER BY v.data DESC, v.id DESC LIMIT 10""", (cid,))
    return jsonify({"cliente": dict(row), "resumo": resumo, "compras": compras})


def _salvar_cliente(cliente, cid=None):
    if not pode_editar(cliente):
        return jsonify({"erro": "Esta base está em modo somente leitura (por exemplo, na Vercel). "
                                "Cadastre clientes rodando o dashboard no seu computador."}), 403
    erros, c = validar_cliente(request.get_json(silent=True) or {})
    if erros:
        return jsonify({"erro": "Verifique os campos destacados.", "campos": erros}), 400
    with conectar(cliente, escrita=True) as con:
        if c["documento"]:
            dup = con.execute("SELECT id, nome FROM clientes WHERE documento = ? AND id IS NOT ?",
                              (c["documento"], cid)).fetchone()
            if dup:
                return jsonify({"erro": "Documento já cadastrado.",
                                "campos": {"documento": f"Já usado por {dup['nome']} (#{dup['id']})."}}), 409
        if cid is None:
            cur = con.execute("""INSERT INTO clientes (nome, documento, cidade, uf, segmento, data_cadastro, ativo)
                                 VALUES (:nome, :documento, :cidade, :uf, :segmento, :data_cadastro, :ativo)""",
                              {**c, "data_cadastro": date.today().isoformat()})
            cid = cur.lastrowid
        else:
            cur = con.execute("""UPDATE clientes SET nome=:nome, documento=:documento, cidade=:cidade, uf=:uf,
                                 segmento=:segmento, ativo=:ativo WHERE id=:id""", {**c, "id": cid})
            if cur.rowcount == 0:
                abort(404)
        con.commit()
        row = dict(con.execute("SELECT * FROM clientes WHERE id = ?", (cid,)).fetchone())
    return jsonify({"cliente": row}), 201 if request.method == "POST" else 200


@app.route("/api/<cliente>/clientes", methods=["POST"])
def api_cliente_criar(cliente):
    return _salvar_cliente(cliente)


@app.route("/api/<cliente>/clientes/<int:cid>", methods=["PUT"])
def api_cliente_atualizar(cliente, cid):
    return _salvar_cliente(cliente, cid)


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", host="127.0.0.1",
            port=int(os.environ.get("PORT", 5000)))
