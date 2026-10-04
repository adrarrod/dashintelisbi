# DashIntelisBI

Dashboard web no estilo **AdminLTE** em que cada cliente tem a sua própria base **SQLite**.
O modelo padrão traz as abas **Visão Geral, Vendas, Orçamento, Clientes, Fornecedores e Análise de Dados**.

## Como rodar

```bash
pip install -r requirements.txt
python scripts/novo_cliente.py --demo   # cria data/techsul.db e data/padaria-central.db com dados fictícios
python app.py                           # abre em http://127.0.0.1:5000
```

O cliente é escolhido no seletor do topo da página; o período (data inicial e final, ou os atalhos 3M/6M/12M/Tudo)
vale para todas as abas e acompanha a navegação.

## Uma base por cliente

- Cada cliente é um arquivo `data/<slug>.db` (ex.: `data/acme.db`). O app lista automaticamente todos os `.db` da pasta.
- Todas as bases seguem o esquema padrão em [`db/schema.sql`](db/schema.sql):
  `empresa`, `clientes`, `fornecedores`, `produtos`, `vendas`, `compras` e `orcamento`.
- Para um cliente novo:
  ```bash
  python scripts/novo_cliente.py acme --nome "ACME Ltda"              # base vazia, pronta para carga
  python scripts/novo_cliente.py acme --nome "ACME Ltda" --exemplo    # já com dados fictícios
  ```
- **Conforme a necessidade:** tabelas ou views extras podem ser criadas só na base daquele cliente.
  Elas aparecem na aba *Análise de Dados* e podem ser consultadas no console SQL sem mudar o código.
- A pasta das bases pode ser trocada com a variável `DASH_DATA_DIR`.

## Abas

| Aba | Conteúdo |
|---|---|
| Visão Geral | faturamento, pedidos, ticket médio, margem, orçamento do ano, faturamento mensal e por categoria, últimas vendas |
| Vendas | faturamento e margem por mês, por canal e por vendedor, top 10 produtos, cancelamentos |
| Orçamento | receita e despesa previsto x realizado por mês e por categoria, com desvio |
| Clientes | cadastrados, ativos, novos, faturamento por segmento, distribuição por UF, maiores clientes |
| Fornecedores | compras por mês e categoria, entregas no prazo, avaliação e ranking |
| Análise de Dados | curva ABC de clientes, margem por categoria, sazonalidade por dia da semana, ticket médio, efeito do desconto e console SQL somente leitura com exportação CSV |

## Estrutura

```
app.py               # Flask: páginas + API JSON (/api/<cliente>/<aba>)
db/schema.sql        # esquema padrão das bases
scripts/novo_cliente.py
templates/           # páginas AdminLTE (Jinja)
static/js/dash.js    # formatação pt-BR, gráficos Chart.js, filtros
data/                # uma base .db por cliente (não versionado)
```

As bases são abertas sempre em modo somente leitura pelo dashboard. AdminLTE 3.2, Bootstrap 4, Chart.js 4 e
Font Awesome são carregados por CDN.
