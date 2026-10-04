# DashIntelisBI

Dashboard web no estilo **AdminLTE** em que cada cliente tem a sua própria base **SQLite**.
O modelo padrão traz as abas **Visão Geral, Vendas, Orçamento, Clientes, Fornecedores e Análise de Dados**.

## Como rodar no seu computador (VS Code)

1. Baixe o projeto: `git clone https://github.com/adrarrod/dashintelisbi.git`
   (ou, no GitHub, **Code → Download ZIP** e descompacte).
2. Abra a pasta no VS Code (**File → Open Folder**) e um terminal (**Terminal → New Terminal**).
3. Crie um ambiente virtual e instale as dependências (precisa do Python 3.10+):
   ```bash
   python -m venv .venv
   # Windows:  .venv\Scripts\activate      macOS/Linux:  source .venv/bin/activate
   pip install -r requirements.txt
   ```
4. Rode `python app.py` e abra http://127.0.0.1:5000.
   Ou aperte **F5** no VS Code (configuração *DashIntelisBI (Flask)* em `.vscode/launch.json`), que roda com
   recarga automática e permite usar breakpoints.

As bases de exemplo `data/techsul.db` e `data/padaria-central.db` já vêm no repositório.
Para recriá-las com dados novos: `python scripts/novo_cliente.py --demo`.

## Publicar na Vercel

O projeto já está no formato que a Vercel reconhece (Flask com `app` em `app.py`, arquivos estáticos em `public/`).

1. Em [vercel.com/new](https://vercel.com/new), importe o repositório `adrarrod/dashintelisbi`.
2. A Vercel detecta Flask sozinha; não precisa mudar nenhuma configuração. Clique em **Deploy**.
3. Cada `git push` gera um novo deploy automaticamente.

Observações:
- Na Vercel o disco é somente leitura e as bases vêm do repositório. O dashboard só lê as bases, então funciona,
  mas para **adicionar ou atualizar um cliente** é preciso colocar o `.db` em `data/`, fazer commit e push.
- Qualquer pessoa com o link vê os dados. Para restringir, ative *Deployment Protection* (Vercel Authentication)
  nas configurações do projeto na Vercel.

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
| Clientes | **Indicadores:** cadastrados, ativos, novos, faturamento por segmento, distribuição por UF, maiores clientes. **Consulta e cadastro:** busca por nome, cidade ou CPF/CNPJ com filtros de segmento, UF e situação; ficha do cliente com últimas compras; cadastro e edição |
| Fornecedores | compras por mês e categoria, entregas no prazo, avaliação e ranking |
| Análise de Dados | curva ABC de clientes, margem por categoria, sazonalidade por dia da semana, ticket médio, efeito do desconto e console SQL somente leitura com exportação CSV |

## Estrutura

```
app.py               # Flask: páginas + API JSON (/api/<cliente>/<aba>)
db/schema.sql        # esquema padrão das bases
scripts/novo_cliente.py
templates/           # páginas AdminLTE (Jinja)
public/static/       # JS e CSS (formatação pt-BR, gráficos Chart.js, filtros)
data/                # uma base .db por cliente
```

O dashboard abre as bases em modo somente leitura; só o cadastro de clientes grava, e apenas quando a base
pode ser escrita (no seu computador). Na Vercel, ou com `DASH_SOMENTE_LEITURA=1`, o cadastro fica bloqueado. AdminLTE 3.2, Bootstrap 4, Chart.js 4 e
Font Awesome são carregados por CDN.
