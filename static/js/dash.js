/* DashIntelisBI: utilitários comuns às páginas (formatação, API, gráficos, filtros). */
(function () {
  'use strict';

  // Paleta categórica validada (ordem fixa; a cor segue a entidade, não a posição).
  const PALETA = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948'];
  const COR = { previsto: '#9aa5b1', realizado: '#2a78d6', bom: '#1e7e34', ruim: '#c0392b' };
  const MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
  const DIAS = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];

  const brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
  const brlCurto = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL', notation: 'compact', maximumFractionDigits: 1 });
  const num = new Intl.NumberFormat('pt-BR');
  const fmt = {
    brl: v => brl.format(v || 0),
    brlCurto: v => brlCurto.format(v || 0),
    num: v => num.format(Math.round(v || 0)),
    pct: (v, casas = 1) => (v == null ? '–' : (v.toFixed(casas).replace('.', ',') + '%')),
    mes: m => { const [a, mm] = m.split('-'); return MESES[+mm - 1] + '/' + a.slice(2); },
    mesNum: (n) => MESES[n - 1],
    // Rótulos de mês; o último ganha '*' quando o período termina no meio do mês.
    meses: (lista, periodo) => lista.map((x, i) => {
      let r = fmt.mes(x.mes);
      if (periodo && i === lista.length - 1 && x.mes === periodo.fim.slice(0, 7)) {
        const [a, m, d] = periodo.fim.split('-').map(Number);
        if (d < new Date(a, m, 0).getDate()) r += '*';
      }
      return r;
    }),
    dia: d => d ? d.split('-').reverse().join('/') : '',
    diaSemana: n => DIAS[n],
    esc: s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])),
  };

  // ---------------------------------------------------------------- Chart.js
  if (window.Chart) {
    Chart.defaults.font.family = '"Source Sans Pro", -apple-system, "Segoe UI", Roboto, sans-serif';
    Chart.defaults.color = '#52514e';
    Chart.defaults.borderColor = 'rgba(0,0,0,.06)';
    Chart.defaults.maintainAspectRatio = false;
    Chart.defaults.plugins.legend.labels.boxWidth = 10;
    Chart.defaults.plugins.legend.labels.boxHeight = 10;
    Chart.defaults.plugins.legend.labels.useBorderRadius = true;
    Chart.defaults.plugins.legend.labels.borderRadius = 2;
    Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(20,20,20,.9)';
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.elements.bar.borderRadius = 4;
    Chart.defaults.elements.line.borderWidth = 2;
    Chart.defaults.elements.point.radius = 0;
    Chart.defaults.elements.point.hoverRadius = 5;
    Chart.defaults.elements.point.hitRadius = 12;
  }
  const graficos = {};

  function grafico(id, config) {
    if (graficos[id]) graficos[id].destroy();
    const el = document.getElementById(id);
    if (!el) return null;
    graficos[id] = new Chart(el, config);
    return graficos[id];
  }

  function barras(id, rotulos, series, opcoes) {
    opcoes = opcoes || {};
    const horizontal = !!opcoes.horizontal;
    const fmtValor = opcoes.formato || fmt.brl;
    const eixoValor = Object.assign({ beginAtZero: true, grid: { color: 'rgba(0,0,0,.05)' }, ticks: { callback: opcoes.formatoEixo || fmt.brlCurto } }, opcoes.eixoValor || {});
    const eixoCat = { grid: { display: false } };
    return grafico(id, {
      type: 'bar',
      data: {
        labels: rotulos,
        datasets: series.map((s, i) => Object.assign({
          backgroundColor: s.cor || PALETA[i], borderColor: '#fff', borderWidth: series.length > 1 ? 1 : 0,
          maxBarThickness: 36, borderSkipped: 'start',
        }, s)),
      },
      options: {
        indexAxis: horizontal ? 'y' : 'x',
        interaction: { mode: 'index', intersect: false, axis: horizontal ? 'y' : 'x' },
        plugins: {
          legend: { display: series.length > 1, position: 'top', align: 'end' },
          tooltip: { callbacks: { label: c => (c.dataset.label ? c.dataset.label + ': ' : '') + fmtValor(horizontal ? c.parsed.x : c.parsed.y) } },
        },
        scales: horizontal ? { x: eixoValor, y: eixoCat } : { x: eixoCat, y: eixoValor },
      },
    });
  }

  function linhas(id, rotulos, series, opcoes) {
    opcoes = opcoes || {};
    const fmtValor = opcoes.formato || fmt.brl;
    return grafico(id, {
      type: 'line',
      data: {
        labels: rotulos,
        datasets: series.map((s, i) => Object.assign({
          borderColor: s.cor || PALETA[i], backgroundColor: (s.cor || PALETA[i]) + '1f',
          tension: 0.3, fill: series.length === 1 && opcoes.area !== false,
        }, s)),
      },
      options: {
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: series.length > 1, position: 'top', align: 'end' },
          tooltip: { callbacks: { label: c => (c.dataset.label ? c.dataset.label + ': ' : '') + fmtValor(c.parsed.y) } },
        },
        scales: {
          x: { grid: { display: false } },
          y: Object.assign({ beginAtZero: true, grid: { color: 'rgba(0,0,0,.05)' }, ticks: { callback: opcoes.formatoEixo || fmt.brlCurto } }, opcoes.eixoY || {}),
        },
      },
    });
  }

  // Rosca com legenda à direita e % no tooltip (até 6 fatias; o resto vira "Outros").
  function rosca(id, itens, opcoes) {
    opcoes = opcoes || {};
    const fmtValor = opcoes.formato || fmt.brl;
    let dados = itens.slice();
    if (dados.length > 6) {
      const outros = dados.slice(5).reduce((s, x) => s + x.valor, 0);
      dados = dados.slice(0, 5).concat([{ rotulo: 'Outros', valor: outros }]);
    }
    const total = dados.reduce((s, x) => s + x.valor, 0) || 1;
    return grafico(id, {
      type: 'doughnut',
      data: {
        labels: dados.map(x => x.rotulo || '(sem)'),
        datasets: [{ data: dados.map(x => x.valor), backgroundColor: dados.map((x, i) => x.rotulo === 'Outros' ? '#b4b2a9' : PALETA[i]), borderColor: '#fff', borderWidth: 2 }],
      },
      options: {
        cutout: '62%',
        plugins: {
          legend: { position: 'right' },
          tooltip: { callbacks: { label: c => `${c.label}: ${fmtValor(c.parsed)} (${fmt.pct(c.parsed / total * 100)})` } },
        },
      },
    });
  }

  // ---------------------------------------------------------------- tabelas
  // colunas: [{campo, titulo?, num?, fmt?}]
  function tabela(tbodyId, registros, colunas) {
    const tb = document.getElementById(tbodyId);
    if (!tb) return;
    if (!registros.length) {
      tb.innerHTML = `<tr><td colspan="${colunas.length}" class="text-center text-muted">Sem dados no período.</td></tr>`;
      return;
    }
    tb.innerHTML = registros.map(r => '<tr>' + colunas.map(c => {
      const v = typeof c.campo === 'function' ? c.campo(r) : r[c.campo];
      const html = c.html ? c.html(r) : fmt.esc(c.fmt ? c.fmt(v) : v);
      return `<td class="${c.num ? 'num' : ''}">${html}</td>`;
    }).join('') + '</tr>').join('');
  }

  function texto(id, valor) {
    const el = document.getElementById(id);
    if (el) el.textContent = valor;
  }

  // ---------------------------------------------------------------- API e filtros
  function parametros() {
    return new URLSearchParams(window.location.search);
  }

  async function api(endpoint, extras) {
    const p = parametros();
    Object.entries(extras || {}).forEach(([k, v]) => p.set(k, v));
    const url = `/api/${encodeURIComponent(DASH.cliente)}/${endpoint}?${p.toString()}`;
    const resp = await fetch(url);
    if (!resp.ok) throw new Error(`Falha ao carregar dados (${resp.status})`);
    return resp.json();
  }

  function mostrarErro(e) {
    const el = document.getElementById('erro-carga');
    el.textContent = e.message || String(e);
    el.classList.remove('d-none');
  }

  // Carrega a página: busca dados, chama render(dados) e mantém o filtro de período sincronizado.
  async function iniciar(endpoint, render) {
    const conteudo = document.querySelector('.content .container-fluid');
    async function carregar() {
      conteudo.classList.add('carregando');
      try {
        const dados = await api(endpoint);
        if (dados.periodo) {
          const i = document.getElementById('f-inicio'), f = document.getElementById('f-fim');
          if (i) i.value = dados.periodo.inicio;
          if (f) f.value = dados.periodo.fim;
        }
        render(dados);
      } catch (e) {
        mostrarErro(e);
      } finally {
        conteudo.classList.remove('carregando');
      }
    }
    const form = document.getElementById('filtro-periodo');
    if (form) {
      form.addEventListener('submit', ev => {
        ev.preventDefault();
        const p = parametros();
        ['inicio', 'fim'].forEach(k => { const v = form.elements[k].value; v ? p.set(k, v) : p.delete(k); });
        history.replaceState(null, '', '?' + p.toString());
        atualizarLinks();
        carregar();
      });
      form.querySelectorAll('[data-meses]').forEach(btn => btn.addEventListener('click', () => {
        const meses = +btn.dataset.meses;
        const fim = form.elements.fim.value || new Date().toISOString().slice(0, 10);
        if (meses === 0) {
          form.elements.inicio.value = '2000-01-01';
        } else {
          const d = new Date(fim + 'T00:00:00');
          d.setMonth(d.getMonth() - meses + 1, 1);
          form.elements.inicio.value = d.toISOString().slice(0, 10);
        }
        form.requestSubmit();
      }));
    }
    await carregar();
    return carregar;
  }

  // Leva o período selecionado ao navegar entre páginas e ao trocar de cliente.
  function atualizarLinks() {
    const q = window.location.search;
    document.querySelectorAll('a[data-pagina]').forEach(a => { a.href = a.href.split('?')[0] + q; });
  }

  document.addEventListener('DOMContentLoaded', () => {
    atualizarLinks();
    const sel = document.getElementById('seletor-cliente');
    if (sel) sel.addEventListener('change', () => {
      window.location.href = `/c/${encodeURIComponent(sel.value)}/${DASH.pagina}${window.location.search}`;
    });
  });

  window.Dash = { PALETA, COR, fmt, grafico, barras, linhas, rosca, tabela, texto, api, iniciar, mostrarErro };
})();
