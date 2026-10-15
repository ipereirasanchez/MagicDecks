/* Guía de Pokémon Z — aplicación (sin dependencias). Lee window.GUIDE_Z (data/data.js). */
(function () {
  'use strict';

  const D = window.GUIDE_Z;
  const $main = document.getElementById('main');
  const $nav = document.getElementById('navLinks');
  const $search = document.getElementById('searchInput');
  const TITLE = 'Guía de Pokémon Z';

  // ------------------------------------------------------------------
  // Utilidades
  // ------------------------------------------------------------------
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const norm = (s) => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const plain = (h) => { const d = document.createElement('div'); d.innerHTML = h; return d.textContent || ''; };
  const titleCase = (s) => String(s).toLowerCase().replace(/(^|[\s\-/(.])([a-záéíóúñ])/g, (m, p, c) => p + c.toUpperCase());

  const SPRITE_HOME = 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/home/';
  const SPRITE_PX = 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/';
  const TYPE_COLORS = {
    normal: '#9a9a7a', fuego: '#e8632b', agua: '#4f8ee8', planta: '#5fb84a', electrico: '#d9ad1c', hielo: '#73c9c7', lucha: '#b8362c',
    veneno: '#9344a0', tierra: '#cfa74a', volador: '#8f9ce6', psiquico: '#e8558b', bicho: '#9bb02a', roca: '#a8933b', fantasma: '#6a5a9e',
    dragon: '#6a44e8', siniestro: '#5a4a44', acero: '#8f8fa8', hada: '#e58fe0',
  };
  const GROUPS = ['Antes de empezar', 'Acto I', 'Acto II', 'Acto III', 'Después de la historia', 'Apéndices'];
  const CHAPTERS = D.nav;
  const chapterIndex = (id) => CHAPTERS.findIndex((c) => c.id === id);

  function spriteInfo(name) {
    return D.sprites[name] || D.sprites[titleCase(name)] || null;
  }

  function spriteHTML(name, size, cls) {
    const s = spriteInfo(name) || { id: null, badge: '' };
    const badge = s.badge ? `<span class="badge">${esc(s.badge)}</span>` : '';
    if (!s.id) {
      return `<span class="pk-img ${cls || ''}"><span class="ph" title="Pokémon nuevo de este juego, sin sprite oficial">Z</span>${badge}</span>`;
    }
    return `<span class="pk-img ${cls || ''}"><img loading="lazy" decoding="async" width="${size}" height="${size}" alt="" src="${SPRITE_HOME}${s.id}.png" data-fallback="${SPRITE_PX}${s.id}.png">${badge}</span>`;
  }

  // Si falla el render HOME se usa el sprite clásico y, si también falla, el marcador.
  document.addEventListener('error', (e) => {
    const img = e.target;
    if (!(img instanceof HTMLImageElement)) return;
    const fb = img.getAttribute('data-fallback');
    if (fb) { img.removeAttribute('data-fallback'); img.src = fb; return; }
    img.replaceWith(Object.assign(document.createElement('span'), { className: 'ph', textContent: 'Z' }));
  }, true);

  function typeChip(t) {
    const c = TYPE_COLORS[norm(t)] || '#777';
    return `<span class="type" style="--tc:${c}">${esc(t)}</span>`;
  }

  function parseHash() {
    const h = location.hash.replace(/^#/, '') || '/';
    const [path, qs] = h.split('?');
    const parts = path.split('/').filter(Boolean);
    const q = Object.fromEntries(new URLSearchParams(qs || ''));
    return { parts, q, path };
  }

  // ------------------------------------------------------------------
  // Navegación lateral
  // ------------------------------------------------------------------
  function renderNav() {
    const { parts } = parseHash();
    const cur = parts[0] === 'c' ? parts[1] : null;
    const html = GROUPS.map((g) => {
      const items = CHAPTERS.filter((c) => c.group === g);
      if (!items.length) return '';
      const open = items.some((c) => c.id === cur) || g === 'Antes de empezar';
      return `
        <details class="nav-group" ${open ? 'open' : ''}>
          <summary>${esc(g)}<span class="n">${items.length}</span></summary>
          ${items.map((c) => `<a class="nav-link ${c.id === cur ? 'active' : ''}" href="#/c/${c.id}">${esc(c.title)}</a>`).join('')}
        </details>`;
    }).join('');
    $nav.innerHTML = `<a class="nav-link nav-home ${parts.length === 0 ? 'active' : ''}" href="#/">Índice</a>${html}`;
  }

  // ------------------------------------------------------------------
  // Bloques
  // ------------------------------------------------------------------
  const CALLOUT = {
    note: ['Nota', 'note'], important: ['Importante', 'important'], tip: ['Pista', 'tip'],
    tips: ['Consejos', 'tips'], quest: ['Misión secundaria', 'quest'],
  };

  function stripLabel(html) {
    // quita la etiqueta inicial ("Nota:", "PISTAS PARA ENTRENADORES:") que ya muestra el callout
    return html.replace(/^(<strong>)?\s*(nota( \d+)?|importante|pistas? (para|de) entrenador(es)?|dato útil|consejos de (batalla|combate)|misi[oó]n secundaria|¡aviso!)\s*:?\s*(<\/strong>)?\s*/i, '');
  }

  function renderParagraph(b) {
    if (b.kind && CALLOUT[b.kind]) {
      const [label, cls] = CALLOUT[b.kind];
      const body = stripLabel(b.html);
      return `<aside class="callout ${cls}"><span class="callout-label">${label}</span><p>${body || '&nbsp;'}</p></aside>`;
    }
    return `<p${b.center ? ' class="narr"' : ''}>${b.html}</p>`;
  }

  function renderList(b) {
    if (b.kind === 'wild') {
      return `<ul class="wild">${b.items.map((it) => {
        if (!it.mon) return `<li class="wild-item plain">${it.html}</li>`;
        let rest = plain(it.html).replace(it.pct, '').replace(it.mon, '').replace(/^[\s.:,()-]+/, '').trim();
        rest = rest.replace(/^\(\s*/, '').replace(/\s*\)\.?\s*$/, '').replace(/^\.\s*/, '');
        return `<li class="wild-item">${spriteHTML(it.mon, 48, 'sm')}<span class="wild-body"><span class="wild-name">${esc(it.mon)}<span class="pct">${esc(it.pct)}</span></span>${rest ? `<span class="wild-drop">${esc(rest)}</span>` : ''}</span></li>`;
      }).join('')}</ul>`;
    }
    return `<ul class="list">${b.items.map((it) => `<li>${it.mon ? spriteHTML(it.mon, 40, 'xs') : ''}<span>${it.html}</span></li>`).join('')}</ul>`;
  }

  function renderBoss(b) {
    return `<div class="roster">${b.mons.map((m) => {
      const name = m.name === '?' ? 'Pokémon sin identificar' : m.name;
      const unk = m.name === '?';
      return `
        <figure class="mon">
          <div class="frame">${unk ? '<span class="pk-img"><span class="ph">?</span></span>' : spriteHTML(m.name, 96, 'lg')}</div>
          <figcaption class="plaque">
            <span class="mon-name">${esc(name)}</span>
            <span class="mon-level">Nv. ${esc(m.level)}</span>
            ${m.types.length ? `<span class="mon-types">${m.types.map(typeChip).join('')}</span>` : ''}
            <dl class="mon-data">
              <dt>Objeto</dt><dd>${esc(titleCase(m.item || '—'))}</dd>
              <dt>Habilidad</dt><dd>${esc(titleCase(m.ability || '—'))}</dd>
              <dt>Naturaleza</dt><dd>${esc(m.nature ? m.nature.replace(/ATK\. ?ESP/gi, 'At. esp.').replace(/DEF\. ?ESP/gi, 'Def. esp.').replace(/ATK/gi, 'Ataque').replace(/DEF/gi, 'Defensa').replace(/VEL/gi, 'Velocidad').replace(/NEUTRA/gi, 'Neutra') : '—')}</dd>
            </dl>
            ${m.moves.length ? `<ul class="moves">${m.moves.map((mv) => `<li>${esc(titleCase(mv))}</li>`).join('')}</ul>` : ''}
          </figcaption>
        </figure>`;
    }).join('')}</div>`;
  }

  const STAT_LABELS = ['PS', 'Ataque', 'Defensa', 'At. esp.', 'Def. esp.', 'Velocidad'];
  function renderStats(b) {
    const hasHidden = b.rows.some((r) => r.hidden);
    return `<div class="tablewrap"><table class="stats">
      <thead><tr><th>Pokémon</th>${STAT_LABELS.map((l) => `<th class="num">${l}</th>`).join('')}<th class="num">Total</th><th>Habilidad</th>${hasHidden ? '<th>Oculta</th>' : ''}</tr></thead>
      <tbody>${b.rows.map((r) => `<tr>
        <td class="name">${spriteHTML(r.name, 40, 'xs')}<span>${esc(r.name)}</span></td>
        ${r.stats.map((v) => `<td class="num"><span class="bar" style="--v:${Math.min(v, 200) / 2}%"></span>${v}</td>`).join('')}
        <td class="num total">${r.stats.reduce((a, c) => a + c, 0)}</td>
        <td>${esc(titleCase(r.ability || '—'))}</td>${hasHidden ? `<td>${esc(titleCase(r.hidden || '—'))}</td>` : ''}
      </tr>`).join('')}</tbody></table></div>`;
  }

  function renderTable(b, filter) {
    const f = norm(filter || '');
    const rows = f ? b.rows.filter((r) => norm(r.join(' ')).includes(f)) : b.rows;
    return `<div class="tablewrap"><table class="two">
      <thead><tr><th>${esc(b.head[0] === 'Mts' ? 'MT' : b.head[0])}</th><th>${esc(b.head[1])}</th></tr></thead>
      <tbody>${rows.map(([a, c]) => `<tr><td class="key">${esc(a)}</td><td>${esc(c)}</td></tr>`).join('') || `<tr><td colspan="2" class="empty">Ninguna coincide con «${esc(filter)}».</td></tr>`}</tbody></table></div>`;
  }

  function renderDex(b, filter) {
    const f = norm(filter || '');
    const rows = f ? b.rows.filter((r) => norm(r.num + ' ' + r.name + ' ' + r.how).includes(f)) : b.rows;
    if (!rows.length) return `<p class="empty">Ningún Pokémon coincide con «${esc(filter)}» en esta generación.</p>`;
    return `<ul class="dex">${rows.map((r) => `<li><span class="dex-num">${esc(r.num)}</span>${spriteHTML(r.name, 56, 'md')}<span class="dex-body"><span class="dex-name">${esc(r.name)}</span><span class="dex-how">${esc(r.how)}</span></span></li>`).join('')}</ul>`;
  }

  function renderBlocks(blocks, filter) {
    let out = '';
    for (const b of blocks) {
      switch (b.t) {
        case 'h':
          if (b.level === 1) out += `<h2 id="${esc(b.id)}" class="sec">${esc(b.text)}</h2>`;
          else if (b.level === 2) out += `<h2 id="${esc(b.id)}" class="sec">${esc(b.text)}</h2>`;
          else if (b.level === 3) out += `<h3 id="${esc(b.id)}">${esc(b.text)}</h3>`;
          else out += `<h4>${esc(b.text)}</h4>`;
          break;
        case 'p': out += renderParagraph(b); break;
        case 'ul': out += renderList(b); break;
        case 'boss': out += renderBoss(b); break;
        case 'stats': out += renderStats(b); break;
        case 'table': out += renderTable(b, filter); break;
        case 'dex': out += renderDex(b, filter); break;
      }
    }
    return out;
  }

  // ------------------------------------------------------------------
  // Páginas
  // ------------------------------------------------------------------
  function pageHome() {
    const nBoss = Object.values(D.chapters).reduce((n, c) => n + c.blocks.filter((b) => b.t === 'boss').reduce((m, b) => m + b.mons.length, 0), 0);
    const nSections = CHAPTERS.reduce((n, c) => n + c.sections.length, 0);
    const route = (g) => CHAPTERS.filter((c) => c.group === g);
    const stop = (c, i) => `
      <li class="stop">
        <a class="stop-title" href="#/c/${c.id}"><span class="stop-dot" aria-hidden="true"></span>${esc(c.title)}</a>
        ${c.sections.length > 1 ? `<p class="stop-sections">${c.sections.filter((s) => s.level === 2 || c.sections.length < 4).slice(0, 14).map((s) => `<a href="#/c/${c.id}/${s.id}">${esc(cleanTitle(s.title))}</a>`).join('')}${c.sections.length > 14 ? `<a class="more" href="#/c/${c.id}">y ${c.sections.length - 14} más</a>` : ''}</p>` : ''}
      </li>`;
    return `
      <section class="hero">
        <p class="kicker">Guía oficial del fangame de Eric_Lostie, reordenada para leerla mientras juegas</p>
        <h1>Pokémon Z</h1>
        <p class="lead">Las ${D.meta.pages} páginas de la guía, partidas por actos y medallas: cada capítulo lleva su propio índice de lugares, los equipos de los jefes van en fichas y la Pokédex, las MTs y las megapiedras se pueden filtrar.</p>
        <div class="hero-actions">
          <a class="btn btn-primary" href="#/c/c01">Empezar por Pueblo Lienzo</a>
          <a class="btn" href="#/c/pokedex">Buscar un Pokémon</a>
          <a class="btn" href="#/c/dudas">Tengo un problema</a>
        </div>
        <p class="facts">${CHAPTERS.length} capítulos, ${nSections} lugares y ${nBoss} Pokémon de jefe con su equipo.</p>
      </section>

      ${GROUPS.map((g) => `
        <section class="act">
          <h2 class="act-title">${esc(g)}</h2>
          <ol class="route">${route(g).map(stop).join('')}</ol>
        </section>`).join('')}

      <section class="about">
        <h2>De dónde sale esto</h2>
        <p>El texto es el de la <em>Guía Oficial de Pokémon Z</em> (Poki_Papillon, Taighean, AlexReshi y el resto del equipo; los créditos completos están al final). Se ha convertido automáticamente desde el PDF: los equipos de los jefes, que en la guía van como imágenes, se han identificado uno a uno y se muestran con los sprites oficiales de PokeAPI. Los Pokémon nuevos del juego no tienen sprite y salen con una Z.</p>
      </section>`;
  }

  // El primer encabezado del capítulo repite el título del PDF ("Xerneas", "POSTGAME"): no se muestra dos veces.
  function skipTitle(c) {
    const b = c.blocks[0];
    if (b && b.t === 'h' && (b.level === 1 || norm(b.text) === norm(c.title))) return c.blocks.slice(1);
    return c.blocks;
  }

  function cleanTitle(t) {
    return t.replace(/\s*\((Opcional|opcional|OPCIONAL)\)\s*$/, '').replace(/:$/, '');
  }

  function pageChapter(id, sectionId, filter) {
    const c = D.chapters[id];
    if (!c) return null;
    const k = chapterIndex(id);
    const nav = CHAPTERS[k];
    const prev = CHAPTERS[k - 1];
    const next = CHAPTERS[k + 1];
    const inGroup = CHAPTERS.filter((x) => x.group === c.group);
    const pos = inGroup.indexOf(nav) + 1;
    const filterable = c.blocks.some((b) => (b.t === 'table' || b.t === 'dex'));
    const sections = nav.sections.filter((s) => s.level === 2 || nav.sections.length < 4);
    return `
      <article class="chapter">
        <header class="chapter-head">
          <p class="kicker">${esc(c.group)}${inGroup.length > 1 ? `, capítulo ${pos} de ${inGroup.length}` : ''}</p>
          <h1>${esc(c.title)}</h1>
          ${filterable ? `<label class="filter"><span>Filtrar</span><input id="pageFilter" type="search" value="${esc(filter || '')}" placeholder="Nombre, lugar o movimiento…" autocomplete="off"></label>` : ''}
          ${sections.length > 1 ? `<nav class="toc" aria-label="En esta página"><p class="toc-title">En esta página</p><ol>${sections.map((s) => `<li><a href="#/c/${id}/${s.id}">${esc(cleanTitle(s.title))}</a></li>`).join('')}</ol></nav>` : ''}
        </header>
        <div class="prose">${renderBlocks(skipTitle(c), filter)}</div>
        <footer class="chapter-foot">
          ${prev ? `<a class="pager prev" href="#/c/${prev.id}"><span>Anterior</span><strong>${esc(prev.title)}</strong></a>` : '<span></span>'}
          ${next ? `<a class="pager next" href="#/c/${next.id}"><span>Siguiente</span><strong>${esc(next.title)}</strong></a>` : ''}
        </footer>
      </article>`;
  }

  // ------------------------------------------------------------------
  // Búsqueda
  // ------------------------------------------------------------------
  let INDEX = null;
  function buildIndex() {
    INDEX = [];
    for (const c of CHAPTERS) {
      const ch = D.chapters[c.id];
      let section = null;
      let label = null;
      for (const b of ch.blocks) {
        if (b.t === 'h') {
          if (b.level <= 3) section = b;
          if (b.level === 4) label = b.text; else label = null;
          INDEX.push({ c, section: b.level <= 3 ? b : section, text: b.text, kind: 'Encabezado', w: 3 });
        } else if (b.t === 'p') {
          INDEX.push({ c, section, text: plain(b.html), kind: 'Texto', w: 1 });
        } else if (b.t === 'ul') {
          for (const it of b.items) INDEX.push({ c, section, text: plain(it.html), kind: it.mon ? 'Pokémon' : 'Lista', w: it.mon ? 2 : 1 });
        } else if (b.t === 'boss') {
          for (const m of b.mons) INDEX.push({ c, section, text: `${m.name} (nivel ${m.level}) ${label ? 'de ' + label : ''} — ${titleCase(m.item)}, ${titleCase(m.ability)}, ${m.moves.map(titleCase).join(', ')}`, kind: 'Combate', w: 2 });
        } else if (b.t === 'stats') {
          for (const r of b.rows) INDEX.push({ c, section, text: `${r.name}: ${r.stats.join('/')} ${titleCase(r.ability)} ${titleCase(r.hidden)}`, kind: 'Stats', w: 2 });
        } else if (b.t === 'table') {
          for (const r of b.rows) INDEX.push({ c, section, text: `${r[0]}: ${r[1]}`, kind: b.kind === 'mt' ? 'MT' : 'Megapiedra', w: 2 });
        } else if (b.t === 'dex') {
          for (const r of b.rows) INDEX.push({ c, section, text: `${r.num} ${r.name}: ${r.how}`, kind: 'Pokédex', w: 2 });
        }
      }
    }
    for (const e of INDEX) e.n = norm(e.text);
  }

  function pageSearch(q) {
    const query = (q.q || '').trim();
    if (!INDEX) buildIndex();
    const terms = norm(query).split(/\s+/).filter(Boolean);
    let hits = [];
    if (terms.length) {
      for (const e of INDEX) {
        if (terms.every((t) => e.n.includes(t))) {
          const first = e.n.indexOf(terms[0]);
          hits.push({ e, score: e.w * 10 - Math.min(first, 200) / 50 + (e.n.startsWith(terms[0]) ? 5 : 0) });
        }
      }
      hits.sort((a, b) => b.score - a.score);
    }
    const shown = hits.slice(0, 80);
    const snippet = (text) => {
      const n = norm(text);
      const i = Math.max(0, n.indexOf(terms[0]) - 60);
      let s = text.slice(i, i + 220);
      if (i > 0) s = '…' + s;
      if (i + 220 < text.length) s += '…';
      return esc(s).replace(new RegExp('(' + terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')', 'gi'), '<mark>$1</mark>');
    };
    return `
      <div class="page-head"><h1>Buscar</h1>
        <p>${query ? (hits.length ? `${hits.length} resultado${hits.length === 1 ? '' : 's'} para «${esc(query)}»${hits.length > 80 ? ', se muestran los 80 primeros' : ''}.` : `Nada contiene «${esc(query)}». Prueba con el nombre del Pokémon, del lugar o del objeto.`) : 'Escribe en el cuadro de la izquierda: busca en el texto de la guía, los equipos de los jefes, la Pokédex y las tablas.'}</p>
      </div>
      <ol class="results">${shown.map(({ e }) => `
        <li><a href="#/c/${e.c.id}${e.section ? '/' + e.section.id : ''}">
          <span class="res-kind">${esc(e.kind)}</span>
          <span class="res-where">${esc(e.c.title)}${e.section && e.section.text !== e.c.title ? ` › ${esc(cleanTitle(e.section.text))}` : ''}</span>
          <span class="res-text">${snippet(e.text)}</span>
        </a></li>`).join('')}</ol>`;
  }

  // ------------------------------------------------------------------
  // Router
  // ------------------------------------------------------------------
  function render(keepScroll) {
    const { parts, q } = parseHash();
    const [p0, p1, p2] = parts;
    let html, title = TITLE, target = null;
    if (!p0) html = pageHome();
    else if (p0 === 'c') {
      html = pageChapter(p1, p2, q.f);
      if (html) { title = `${CHAPTERS[chapterIndex(p1)].title} · ${TITLE}`; target = p2 || null; }
    } else if (p0 === 'buscar') { html = pageSearch(q); title = `Buscar · ${TITLE}`; }
    if (!html) html = `<div class="empty-page"><h1>Esta página no existe</h1><p><a href="#/">Volver al índice</a></p></div>`;
    document.title = title;
    $main.innerHTML = html;
    renderNav();
    wireFilter();
    closeSidebar();
    if (target) {
      const el = document.getElementById(target);
      if (el) { el.scrollIntoView({ block: 'start' }); el.classList.add('flash'); return; }
    }
    if (!keepScroll) window.scrollTo(0, 0);
  }

  function wireFilter() {
    const inp = document.getElementById('pageFilter');
    if (!inp) return;
    let t;
    inp.addEventListener('input', () => {
      clearTimeout(t);
      t = setTimeout(() => {
        const { path, q } = parseHash();
        const nq = { ...q, f: inp.value };
        if (!nq.f) delete nq.f;
        const qs = new URLSearchParams(nq).toString();
        history.replaceState(null, '', '#' + path + (qs ? '?' + qs : ''));
        render(true);
        const el = document.getElementById('pageFilter');
        if (el) { el.focus(); el.setSelectionRange(el.value.length, el.value.length); }
      }, 160);
    });
  }

  // ------------------------------------------------------------------
  // Chrome: menú móvil, tema, búsqueda global
  // ------------------------------------------------------------------
  const $sidebar = document.getElementById('sidebar');
  const $scrim = document.getElementById('scrim');
  const $menuBtn = document.getElementById('menuBtn');
  function openSidebar() { $sidebar.classList.add('open'); $scrim.hidden = false; $menuBtn.setAttribute('aria-expanded', 'true'); }
  function closeSidebar() { $sidebar.classList.remove('open'); $scrim.hidden = true; $menuBtn.setAttribute('aria-expanded', 'false'); }
  $menuBtn.addEventListener('click', () => ($sidebar.classList.contains('open') ? closeSidebar() : openSidebar()));
  $scrim.addEventListener('click', closeSidebar);

  const $themeBtn = document.getElementById('themeBtn');
  function applyTheme(t) {
    if (t === 'light') document.documentElement.setAttribute('data-theme', 'light');
    else if (t === 'dark') document.documentElement.setAttribute('data-theme', 'dark');
    else document.documentElement.removeAttribute('data-theme');
  }
  let theme = null;
  try { theme = localStorage.getItem('z-theme'); } catch (e) { theme = null; }
  applyTheme(theme);
  $themeBtn.addEventListener('click', () => {
    const dark = document.documentElement.getAttribute('data-theme') === 'dark'
      || (!document.documentElement.getAttribute('data-theme') && matchMedia('(prefers-color-scheme: dark)').matches);
    theme = dark ? 'light' : 'dark';
    applyTheme(theme);
    try { localStorage.setItem('z-theme', theme); } catch (e) { /* sin almacenamiento */ }
  });

  let st;
  $search.addEventListener('input', () => {
    clearTimeout(st);
    st = setTimeout(() => {
      const v = $search.value.trim();
      if (v) location.hash = '/buscar?q=' + encodeURIComponent(v);
    }, 250);
  });
  $search.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') { const v = $search.value.trim(); if (v) location.hash = '/buscar?q=' + encodeURIComponent(v); }
    if (e.key === 'Escape') { $search.value = ''; $search.blur(); }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === '/' && !/input|textarea/i.test(document.activeElement.tagName)) { e.preventDefault(); $search.focus(); $search.select(); }
  });

  window.addEventListener('hashchange', () => {
    const { parts, q } = parseHash();
    if (parts[0] === 'buscar') $search.value = q.q || '';
    render();
  });
  const first = parseHash();
  if (first.parts[0] === 'buscar') $search.value = first.q.q || '';
  render();
})();
