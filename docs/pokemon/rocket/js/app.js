/* Guía Team Rocket Edition — aplicación (sin dependencias) */
(function () {
  'use strict';

  const D = window.GUIDE_DATA;
  const $main = document.getElementById('main');
  const $nav = document.getElementById('navLinks');
  const $search = document.getElementById('searchInput');

  // ------------------------------------------------------------------
  // Utilidades
  // ------------------------------------------------------------------
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const norm = (s) => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const titleCase = (s) => String(s).toLowerCase().replace(/(^|[\s\-/(.])([a-záéíóúñ])/g, (m, p, c) => p + c.toUpperCase());

  const SPRITE_HOME = 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/home/';
  const SPRITE_PX = 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/';

  const SEASON_COLOR = { t1: 'var(--s-kanto)', t2: 'var(--s-archi7)', t3: 'var(--s-johto)', t4: 'var(--s-dlc)', t5: 'var(--s-hoenn)' };
  const STAGE_COLOR = { T1: 'var(--s-kanto)', T2: 'var(--s-archi7)', T3: 'var(--s-johto)', T4: 'var(--s-dlc)', T5: 'var(--s-hoenn)' };
  const DIFF_LABEL = { facil: 'Fácil', normal: 'Normal', dificil: 'Difícil' };
  const STAT_LABELS = ['PS', 'Ataque', 'Defensa', 'At. Esp.', 'Def. Esp.', 'Velocidad'];
  const STAT_SHORT = ['PS', 'At', 'Def', 'AtE', 'DefE', 'Vel'];
  const TYPE_COLORS = {
    normal: '#9a9a7a', fuego: '#e8632b', agua: '#4f8ee8', planta: '#5fb84a', electrico: '#e0b321', hielo: '#73c9c7', lucha: '#b8362c',
    veneno: '#9344a0', tierra: '#cfa74a', volador: '#8f9ce6', psiquico: '#e8558b', bicho: '#9bb02a', roca: '#a8933b', fantasma: '#6a5a9e',
    dragon: '#6a44e8', siniestro: '#5a4a44', acero: '#8f8fa8', hada: '#e58fe0',
  };

  function spriteInfo(name) {
    const s = D.sprites[name] || D.sprites[titleCase(name)] || D.sprites[String(name).toUpperCase()] || null;
    return s || { id: null, badge: '' };
  }

  function spriteHTML(name, size, cls) {
    return spriteFromInfo(spriteInfo(name), size, cls);
  }

  function spriteFromInfo(s, size, cls) {
    s = s || { id: null, badge: '' };
    const badge = s.badge ? `<span class="badge">${esc(s.badge)}</span>` : '';
    if (!s.id) {
      return `<div class="pk-img ${cls || ''}"><span class="ph" title="Sin sprite oficial">R</span>${badge}</div>`;
    }
    return `<div class="pk-img ${cls || ''}"><img loading="lazy" decoding="async" width="${size}" height="${size}" alt="" src="${SPRITE_HOME}${s.id}.png" data-fallback="${SPRITE_PX}${s.id}.png">${badge}</div>`;
  }

  // Imágenes: si falla el render HOME se usa el sprite clásico y, si también falla, el marcador "R".
  document.addEventListener('error', (e) => {
    const img = e.target;
    if (!(img instanceof HTMLImageElement)) return;
    const fb = img.getAttribute('data-fallback');
    if (fb) { img.removeAttribute('data-fallback'); img.src = fb; return; }
    const wrap = img.parentElement;
    if (wrap) { img.replaceWith(Object.assign(document.createElement('span'), { className: 'ph', textContent: 'R' })); }
  }, true);

  function typeChip(t) {
    if (!t) return '';
    return t.split('/').map((x) => {
      const k = norm(x.trim());
      const c = TYPE_COLORS[k] || '#777';
      return `<span class="type" style="background:${c}">${esc(x.trim())}</span>`;
    }).join(' ');
  }

  function stagePill(stage) {
    if (!stage) return '';
    const key = stage.slice(0, 2).toUpperCase();
    return `<span class="pill stage" style="background:${STAGE_COLOR[key] || 'var(--line-2)'}">${esc(stage)}</span>`;
  }

  function parseHash() {
    const h = location.hash.replace(/^#/, '') || '/';
    const [path, qs] = h.split('?');
    const parts = path.split('/').filter(Boolean);
    const q = Object.fromEntries(new URLSearchParams(qs || ''));
    return { parts, q, path };
  }

  function setQuery(patch) {
    const { path, q } = parseHash();
    const nq = { ...q, ...patch };
    Object.keys(nq).forEach((k) => (nq[k] === '' || nq[k] == null) && delete nq[k]);
    const qs = new URLSearchParams(nq).toString();
    history.replaceState(null, '', '#' + path + (qs ? '?' + qs : ''));
  }

  // ------------------------------------------------------------------
  // Navegación lateral
  // ------------------------------------------------------------------
  const ICONS = {
    home: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M3 11 12 3l9 8v10h-6v-6H9v6H3z"/></svg>',
    battle: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="m4 20 6-6M14 4l6 6M4 4l16 16M14 20l6-6M4 10l6-6"/></svg>',
    dex: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M3 12h6M15 12h6"/><circle cx="12" cy="12" r="3"/></svg>',
    evo: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 12h12M12 6l6 6-6 6"/></svg>',
    new: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="m12 3 2.6 5.6 6 .7-4.5 4.1 1.2 6L12 16.5 6.7 19.4l1.2-6L3.4 9.3l6-.7z"/></svg>',
    stats: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 20V10M10 20V4M16 20v-8M22 20H2"/></svg>',
    moves: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M13 2 4 14h7l-1 8 9-12h-7z"/></svg>',
    items: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M4 8h16v12H4zM2 4h20v4H2zM12 8v12"/></svg>',
    quest: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M9 11l3 3 8-8M20 12v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h9"/></svg>',
    faq: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.7M12 17h.01"/></svg>',
    qol: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M5.6 18.4l2.1-2.1M16.3 7.7l2.1-2.1"/><circle cx="12" cy="12" r="3"/></svg>',
  };

  const NAV = [
    { group: 'Guía', links: [
      { to: '/', label: 'Inicio', icon: 'home' },
      { to: '/combates', label: 'Combates de jefe', icon: 'battle', sub: D.seasons.map((s) => ({ to: `/combates/${s.id}/main`, label: `T${s.num} · ${s.short}`, color: SEASON_COLOR[s.id] })) },
      { to: '/secundarias', label: 'Misiones secundarias', icon: 'quest' },
      { to: '/faq', label: 'Preguntas frecuentes', icon: 'faq' },
      { to: '/qol', label: 'Farmeo y mecánicas', icon: 'qol' },
    ] },
    { group: 'Datos', links: [
      { to: '/pokedex', label: 'Dónde conseguir cada Pokémon', icon: 'dex' },
      { to: '/evoluciones', label: 'Evoluciones cambiadas', icon: 'evo' },
      { to: '/nuevos', label: 'Pokémon nuevos del hack', icon: 'new' },
      { to: '/cambios', label: 'Stats, tipos y habilidades', icon: 'stats' },
      { to: '/movimientos', label: 'Movimientos cambiados', icon: 'moves' },
      { to: '/objetos', label: 'Objetos y MTs', icon: 'items' },
    ] },
  ];

  function renderNav() {
    const { parts } = parseHash();
    const cur = '/' + parts.join('/');
    $nav.innerHTML = NAV.map((g) => `
      <div class="nav-group">
        <div class="nav-group-title">${g.group}</div>
        ${g.links.map((l) => {
          const active = l.to === '/' ? cur === '/' : cur.startsWith(l.to);
          const sub = l.sub && active ? `<div class="nav-sub">${l.sub.map((s) => `<a href="#${s.to}" class="${cur.startsWith(s.to.replace(/\/main$/, '')) ? 'active' : ''}"><i class="dot" style="background:${s.color}"></i>${esc(s.label)}</a>`).join('')}</div>` : '';
          return `<a class="nav-link ${active ? 'active' : ''}" href="#${l.to}">${ICONS[l.icon]}<span>${esc(l.label)}</span></a>${sub}`;
        }).join('')}
      </div>`).join('');
  }

  // ------------------------------------------------------------------
  // Página: inicio
  // ------------------------------------------------------------------
  function countTrainers(season) {
    return ['main', 'side'].reduce((n, k) => n + season[k].reduce((m, sec) => m + sec.trainers.length, 0), 0);
  }

  function pageHome() {
    const nTrainers = D.seasons.reduce((n, s) => n + countTrainers(s), 0);
    const nAvail = D.dex.filter((e) => !e.tags.includes('no-disponible')).length;
    const nMT = D.itemLocations.filter((s) => /MTS/.test(s.title)).reduce((n, s) => n + s.items.length, 0);
    return `
      <section class="hero">
        <div class="hero-kicker">Pokémon Team Rocket Edition · TRE 2026 · Dragonsden</div>
        <h1>De recluta a ejecutivo, sin perderse por el camino.</h1>
        <p>Todo lo que hay en la carpeta de información útil del hack, ordenado para consultarlo mientras juegas: equipos de cada jefe en las tres dificultades, dónde cae cada Pokémon y cada objeto, qué ha cambiado respecto a los juegos oficiales y cómo farmear sin perder tiempo.</p>
        <div class="hero-actions">
          <a class="btn btn-primary" href="#/combates/t1/main">Ver combates de Kanto</a>
          <a class="btn" href="#/pokedex">Buscar un Pokémon</a>
          <a class="btn" href="#/faq">Estoy atascado</a>
        </div>
      </section>

      <section class="section">
        <h2>Las cinco temporadas</h2>
        <p class="lead">La historia avanza por temporadas. Cada una tiene sus combates principales, sus misiones secundarias y un salto de nivel claro.</p>
        <div class="route">
          ${D.seasons.map((s) => `<a href="#/combates/${s.id}/main"><i class="node" style="background:${SEASON_COLOR[s.id]}"></i><span class="t">T${s.num} ${esc(s.short)}</span><span class="s">${s.main.length} tramos · ${countTrainers(s)} jefes</span></a>`).join('')}
        </div>
      </section>

      <section class="section">
        <h2>Qué hay en la guía</h2>
        <div class="tiles">
          ${tile('/combates', 'battle', 'Combates de jefe', 'Equipo completo de cada rival: nivel, objeto, naturaleza, habilidad, movimientos, IVs y EVs. Selector Fácil / Normal / Difícil.', `${nTrainers} entrenadores`)}
          ${tile('/pokedex', 'dex', 'Dónde conseguir cada Pokémon', 'Lista completa con el método de obtención y filtros por salvaje, evolución, regalo, compra o misión.', `${nAvail} obtenibles de ${D.dex.length}`)}
          ${tile('/secundarias', 'quest', 'Misiones secundarias', 'Cómo activarlas, requisitos previos y recompensas, región a región.', `${D.sidequests.reduce((n, r) => n + r.quests.length, 0)} misiones`)}
          ${tile('/objetos', 'items', 'Objetos y MTs', 'Piedras evolutivas, potenciadores, megapiedras, tablas y las 152 MTs con su ubicación y temporada.', `${nMT} MTs localizadas`)}
          ${tile('/nuevos', 'new', 'Pokémon nuevos del hack', 'Experimentos Rocket, Fuertes Vínculo, nuevas megas, formas primigenias y Pokémon beta de Oro y Plata.', `${Object.values(D.newPokemon).reduce((n, g) => n + g.reduce((m, x) => m + x.blocks.length, 0), 0)} formas`)}
          ${tile('/cambios', 'stats', 'Stats, tipos y habilidades', 'Comparativa oficial frente a hack, con barras para ver de un vistazo qué ha subido o bajado.', `${D.statChanges.length} Pokémon retocados`)}
          ${tile('/movimientos', 'moves', 'Movimientos cambiados', 'Potencia, precisión, PP y efectos secundarios antes y después.', `${D.moves.length} movimientos`)}
          ${tile('/evoluciones', 'evo', 'Evoluciones cambiadas', 'Métodos nuevos: Piedra Link, Piedra Sagrada, Piedra Rocket y evoluciones por nivel sin intercambio.', `${D.evolutions.changed.length + D.evolutions.new.length} cambios`)}
          ${tile('/qol', 'qol', 'Farmeo y mecánicas', 'Dinero, experiencia, caramelos, IVs perfectos, mentas, movimientos huevo y recordador.', `${D.qol.sections.filter((s) => !s.heading).length} apartados`)}
          ${tile('/faq', 'faq', 'Preguntas frecuentes', 'Los bloqueos más habituales de la historia principal y cómo salir de ellos.', `${D.faq.items.length} respuestas`)}
        </div>
      </section>`;
  }

  function tile(to, icon, title, desc, count) {
    return `<a class="tile" href="#${to}"><h3>${ICONS[icon]}${esc(title)}</h3><p>${esc(desc)}</p><span class="count">${esc(count)}</span></a>`;
  }

  // ------------------------------------------------------------------
  // Página: combates
  // ------------------------------------------------------------------
  function pageBattlesIndex() {
    return `
      <div class="page-head"><h1>Combates de jefe</h1><p>Elige temporada. Dentro puedes alternar entre los combates de la historia y los de misiones secundarias, y cambiar la dificultad.</p></div>
      <div class="tiles">
        ${D.seasons.map((s) => `<a class="tile" href="#/combates/${s.id}/main" style="border-top:4px solid ${SEASON_COLOR[s.id]}"><h3>T${s.num} · ${esc(s.name)}</h3><p>${s.main.length} tramos de historia, ${s.side.length} secundarias con combate.</p><span class="count">${countTrainers(s)} entrenadores</span></a>`).join('')}
      </div>`;
  }

  function pokemonCard(p) {
    const moves = p.moves.length ? `<div class="pk-moves">${p.moves.map((m) => `<span title="${esc(m)}">${esc(m)}</span>`).join('')}</div>` : '';
    const foot = (p.ivs || p.evs) ? `<div class="pk-foot"><span>IVs ${esc(p.ivs || '—')}</span><span>EVs ${esc(p.evs || '—')}</span></div>` : '';
    const line2 = [p.nature, p.ability].filter(Boolean).map(esc).join(' · ');
    return `
      <article class="pk">
        ${spriteHTML(p.name, 80)}
        <div class="pk-main">
          <div class="pk-name"><b title="${esc(p.name)}">${esc(p.name)}</b><span class="pill lvl">Nv. ${p.level}</span></div>
          <div class="pk-line"><span class="k">Objeto</span> ${p.item ? esc(p.item) : '<span class="muted">ninguno</span>'}</div>
          ${line2 ? `<div class="pk-line">${line2}</div>` : ''}
        </div>
        ${moves}${foot}
      </article>`;
  }

  function trainerCard(t, diff) {
    const team = t.teams[diff] || (diff !== 'normal' ? t.teams.normal : null) || null;
    const fallback = !t.teams[diff] && team ? `<p class="diff-note">No hay datos específicos en ${DIFF_LABEL[diff]}; se muestra el equipo Normal.</p>` : '';
    const levels = team ? team.map((p) => p.level) : [];
    const lvlTxt = levels.length ? (Math.min(...levels) === Math.max(...levels) ? `Nv. ${levels[0]}` : `Nv. ${Math.min(...levels)}–${Math.max(...levels)}`) : '';
    return `
      <article class="trainer" id="${t._id}">
        <header class="trainer-head">
          <h3>${esc(titleCase(t.name))}</h3>
          <div class="meta">${team ? `<span class="pill">${team.length} Pokémon</span>` : ''}${lvlTxt ? `<span class="pill">${lvlTxt}</span>` : ''}</div>
        </header>
        ${t.notes.length ? `<div class="trainer-notes">${t.notes.map((n) => `<span class="pill">⚠ ${esc(n)}</span>`).join('')}</div>` : ''}
        ${fallback ? `<div style="padding:0 18px">${fallback}</div>` : ''}
        ${team ? `<div class="team">${team.map(pokemonCard).join('')}</div>` : '<div class="team empty">Sin datos de equipo para esta dificultad.</div>'}
      </article>`;
  }

  function pageBattles(seasonId, kind, q) {
    const season = D.seasons.find((s) => s.id === seasonId);
    if (!season) return notFound();
    kind = kind === 'side' ? 'side' : 'main';
    const diff = ['facil', 'normal', 'dificil'].includes(q.d) ? q.d : 'normal';
    const filter = norm(q.f || '');
    const sections = season[kind];
    sections.forEach((sec, i) => sec.trainers.forEach((t, j) => (t._id = `${seasonId}-${kind}-${i}-${j}`)));

    const visible = sections.map((sec) => {
      if (!filter) return sec;
      const trainers = sec.trainers.filter((t) => norm(t.name).includes(filter) || norm(sec.title).includes(filter) || Object.values(t.teams).some((team) => team.some((p) => norm(p.name).includes(filter))));
      return { ...sec, trainers };
    }).filter((sec) => sec.trainers.length);

    const toc = sections.map((sec, i) => `<a class="chip" href="#/combates/${seasonId}/${kind}?${new URLSearchParams({ ...q, d: diff }).toString()}#sec-${i}" data-scroll="sec-${i}">${esc(titleCase(sec.title))}</a>`).join(' ');

    return `
      <div class="page-head">
        <div class="crumbs"><a href="#/combates">Combates</a><span>›</span><span>T${season.num} · ${esc(season.name)}</span></div>
        <h1 style="border-left:6px solid ${SEASON_COLOR[season.id]};padding-left:14px">Temporada ${season.num}: ${esc(season.name)}</h1>
      </div>
      <div class="sticky-tools">
        <div class="toolbar">
          <div class="seg" role="group" aria-label="Tipo de combate">
            <button data-kind="main" aria-pressed="${kind === 'main'}">Historia</button>
            <button data-kind="side" aria-pressed="${kind === 'side'}">Secundarias</button>
          </div>
          <div class="seg" role="group" aria-label="Dificultad">
            ${['facil', 'normal', 'dificil'].map((d) => `<button data-d="${d}" aria-pressed="${diff === d}">${DIFF_LABEL[d]}</button>`).join('')}
          </div>
          <input type="search" id="battleFilter" value="${esc(q.f || '')}" placeholder="Filtrar por entrenador, lugar o Pokémon…" aria-label="Filtrar combates">
          <span class="result-count">${visible.reduce((n, s) => n + s.trainers.length, 0)} entrenadores</span>
        </div>
      </div>
      ${!filter ? `<nav class="toc" aria-label="Tramos de la temporada">${toc}</nav>` : ''}
      ${visible.length ? visible.map((sec, i) => `
        <section class="battle-section" id="sec-${sections.indexOf(sec)}">
          <h2>${esc(titleCase(sec.title))} <span class="n">${sec.trainers.length} ${sec.trainers.length === 1 ? 'combate' : 'combates'}</span></h2>
          ${sec.trainers.map((t) => trainerCard(t, diff)).join('')}
        </section>`).join('') : `<div class="empty">Ningún combate coincide con «${esc(q.f)}».</div>`}`;
  }

  function wireBattles() {
    $main.querySelectorAll('[data-kind]').forEach((b) => b.addEventListener('click', () => {
      const { parts, q } = parseHash();
      location.hash = `/combates/${parts[1]}/${b.dataset.kind}?${new URLSearchParams(q).toString()}`;
    }));
    $main.querySelectorAll('[data-d]').forEach((b) => b.addEventListener('click', () => { setQuery({ d: b.dataset.d }); render(); }));
    const inp = document.getElementById('battleFilter');
    if (inp) {
      let t;
      inp.addEventListener('input', () => { clearTimeout(t); t = setTimeout(() => { setQuery({ f: inp.value }); render(true); const el = document.getElementById('battleFilter'); if (el) { el.focus(); el.setSelectionRange(el.value.length, el.value.length); } }, 180); });
    }
    $main.querySelectorAll('[data-scroll]').forEach((a) => a.addEventListener('click', (e) => {
      e.preventDefault();
      const el = document.getElementById(a.dataset.scroll);
      if (el) { const y = el.getBoundingClientRect().top + window.scrollY - 150; window.scrollTo({ top: y, behavior: 'smooth' }); }
    }));
  }

  // ------------------------------------------------------------------
  // Página: Pokédex de obtención
  // ------------------------------------------------------------------
  const DEX_TAGS = [
    ['salvaje', 'Salvaje'], ['evolucion', 'Evolución'], ['regalo', 'Regalo'], ['compra', 'Compra'], ['mision', 'Misión'], ['no-disponible', 'No disponible'],
  ];
  const DEX_PAGE = 90;

  function pageDex(q) {
    const f = norm(q.f || '');
    const tag = q.t || '';
    const excl = q.x === '1';
    const page = parseInt(q.p || '1', 10) || 1;
    const list = D.dex.filter((e) => (!f || norm(e.display).includes(f) || norm(e.how).includes(f) || String(e.num) === f) && (!tag || e.tags.includes(tag)) && (!excl || e.exclusive));
    const shown = list.slice(0, page * DEX_PAGE);
    return `
      <div class="page-head"><h1>Dónde conseguir cada Pokémon</h1><p>Lista completa del hack con su método de obtención. Los que aparecen sin texto no están disponibles en esta versión. Los que no están en la lista de evoluciones cambiadas conservan su método oficial.</p></div>
      <div class="sticky-tools">
        <div class="toolbar">
          <input type="search" id="dexFilter" value="${esc(q.f || '')}" placeholder="Nombre, número o lugar (p. ej. «Zona Safari»)…" aria-label="Filtrar Pokémon">
          <span class="result-count">${list.length} resultados</span>
        </div>
        <div class="filters" style="margin-top:8px">
          ${DEX_TAGS.map(([k, l]) => `<button data-tag="${k}" aria-pressed="${tag === k}">${l}</button>`).join('')}
          <button data-excl="1" aria-pressed="${excl}">Exclusivos del hack</button>
        </div>
      </div>
      ${shown.length ? `<div class="dex-list">${shown.map(dexItem).join('')}</div>` : `<div class="empty">Nada coincide con la búsqueda.</div>`}
      ${shown.length < list.length ? `<div class="more"><button class="btn" id="dexMore">Mostrar ${Math.min(DEX_PAGE, list.length - shown.length)} más (${list.length - shown.length} restantes)</button></div>` : ''}`;
  }

  function dexItem(e) {
    return `
      <article class="dex-item">
        ${spriteFromInfo(e.sprite, 68)}
        <div>
          <div class="dex-head"><span class="num">#${String(e.num).padStart(4, '0')}</span><b>${esc(e.display)}</b></div>
          <div class="dex-how">${e.how ? esc(e.how) : '<span class="muted">No disponible en esta versión.</span>'}</div>
          <div class="dex-tags">${e.tags.map((t) => `<span class="tag tag-${t}">${esc(DEX_TAGS.find((x) => x[0] === t)?.[1] || 'Otro')}</span>`).join('')}${e.exclusive ? '<span class="tag" style="background:var(--rocket);color:#fff">Exclusivo</span>' : ''}</div>
        </div>
      </article>`;
  }

  function wireDex() {
    const inp = document.getElementById('dexFilter');
    let t;
    inp?.addEventListener('input', () => { clearTimeout(t); t = setTimeout(() => { setQuery({ f: inp.value, p: '' }); render(true); const el = document.getElementById('dexFilter'); if (el) { el.focus(); el.setSelectionRange(el.value.length, el.value.length); } }, 180); });
    $main.querySelectorAll('[data-tag]').forEach((b) => b.addEventListener('click', () => { const { q } = parseHash(); setQuery({ t: q.t === b.dataset.tag ? '' : b.dataset.tag, p: '' }); render(true); }));
    $main.querySelector('[data-excl]')?.addEventListener('click', () => { const { q } = parseHash(); setQuery({ x: q.x === '1' ? '' : '1', p: '' }); render(true); });
    document.getElementById('dexMore')?.addEventListener('click', () => { const { q } = parseHash(); setQuery({ p: String((parseInt(q.p || '1', 10) || 1) + 1) }); render(true); });
  }

  // ------------------------------------------------------------------
  // Página: evoluciones
  // ------------------------------------------------------------------
  function evoRow(ev) {
    return `
      <article class="evo">
        ${spriteHTML(ev.from, 52)}
        <span class="arrow" aria-hidden="true">${ev.both ? '⇄' : '→'}</span>
        ${spriteHTML(ev.to, 52)}
        <div class="names"><b>${esc(ev.from)} ${ev.both ? '⇄' : '→'} ${esc(ev.to)}</b></div>
        <div class="method">${esc(ev.method)}${ev.both ? ' · en ambos sentidos' : ''}</div>
      </article>`;
  }

  function pageEvolutions(q) {
    const f = norm(q.f || '');
    const filt = (l) => l.filter((e) => !f || norm(e.from + ' ' + e.to + ' ' + e.method).includes(f));
    const ch = filt(D.evolutions.changed), nw = filt(D.evolutions.new);
    return `
      <div class="page-head"><h1>Evoluciones cambiadas</h1><p>${esc(D.evolutions.note)}. Las piedras nuevas (Link, Sagrada, Rocket, Devon) se encuentran en la sección de objetos.</p></div>
      <div class="toolbar"><input type="search" id="pageFilter" value="${esc(q.f || '')}" placeholder="Filtrar por Pokémon o método…" aria-label="Filtrar evoluciones"><span class="result-count">${ch.length + nw.length} resultados</span></div>
      <section class="section"><h2>Métodos modificados</h2><div class="evo-list">${ch.map(evoRow).join('') || '<div class="empty">Sin resultados.</div>'}</div></section>
      <section class="section"><h2>Evolución de los Pokémon nuevos</h2><div class="evo-list">${nw.map(evoRow).join('') || '<div class="empty">Sin resultados.</div>'}</div></section>`;
  }

  // ------------------------------------------------------------------
  // Comparativa de stats (usada en "cambios" y en "nuevos")
  // ------------------------------------------------------------------
  function statCard(block, opts) {
    const lines = block.lines;
    const max = Math.max(200, ...lines.flatMap((l) => l.stats));
    const classes = ['c0', 'c1', 'c2'];
    const rows = STAT_LABELS.map((lab, i) => `
      <div class="stat-row"><span class="lab" title="${lab}">${STAT_SHORT[i]}</span>
        <div class="bars">${lines.map((l, j) => `<div class="bar" title="${esc(l.label)}: ${l.stats[i]}"><i class="${classes[j] || 'c2'}" style="width:${(l.stats[i] / max * 100).toFixed(1)}%"></i><b>${l.stats[i]}</b></div>`).join('')}</div>
      </div>`).join('');
    const legend = lines.map((l, j) => `<span><i class="${classes[j] || 'c2'}"></i>${esc(l.label)} <span class="tot">${l.total}</span></span>`).join('');
    const spriteName = (opts && opts.spriteName) || block.title;
    const meta = [
      block.type_official ? `<span class="pill">Tipo oficial: ${esc(block.type_official)}</span>` : '',
      block.type ? `<span>${typeChip(block.type)}</span>` : '',
      ...(block.abilities || []).map((a) => `<span class="pill">${esc(a)}</span>`),
    ].filter(Boolean).join('');
    return `
      <article class="stat-card">
        ${spriteHTML(titleCase(spriteName), 92)}
        <div>
          <h3>${esc(titleCase(block.title))}</h3>
          ${meta ? `<div class="stat-meta">${meta}</div>` : ''}
          ${lines.length ? `<div class="stat-rows">${rows}</div><div class="legend">${legend}</div>` : '<p class="muted small" style="margin:6px 0 0">Solo cambian las habilidades o el tipo.</p>'}
        </div>
      </article>`;
  }

  function pageStatChanges(q) {
    const f = norm(q.f || '');
    const list = D.statChanges.filter((b) => !f || norm(b.title).includes(f) || norm((b.abilities || []).join(' ')).includes(f) || norm(b.type || '').includes(f));
    return `
      <div class="page-head"><h1>Stats, tipos y habilidades</h1><p>Comparativa entre el juego oficial (gris) y el hack (rojo). Cuando un Pokémon no muestra barras es porque solo cambian sus habilidades o su tipo.</p></div>
      <div class="toolbar"><input type="search" id="pageFilter" value="${esc(q.f || '')}" placeholder="Filtrar por Pokémon, tipo o habilidad…" aria-label="Filtrar"><span class="result-count">${list.length} Pokémon</span></div>
      <div class="grid grid-2">${list.map((b) => statCard(b)).join('') || '<div class="empty">Sin resultados.</div>'}</div>`;
  }

  // ------------------------------------------------------------------
  // Página: nuevos Pokémon
  // ------------------------------------------------------------------
  const NEW_TABS = [
    ['experimentos', 'Experimentos Rocket', 'Prototipos creados por los científicos del Team Rocket. Sufijos -X / -Y (físico / especial) para los de nivel I y -Z para los de nivel II.'],
    ['vinculo', 'Fuertes Vínculo', 'Formas que alcanzan ciertos Pokémon por el vínculo con su entrenador (sufijo &). Solo el del protagonista es obtenible, de momento.'],
    ['megas', 'Nuevas megaevoluciones', 'Megaevoluciones que no existen en los juegos oficiales. Sus megapiedras se listan en la sección de objetos.'],
    ['antiguos', 'Primigenios y antiguos', 'Pokémon recuperados de la beta de Oro y Plata de 1997, y formas primigenias de legendarios.'],
  ];

  function pageNew(tab) {
    tab = NEW_TABS.some((t) => t[0] === tab) ? tab : 'experimentos';
    const info = NEW_TABS.find((t) => t[0] === tab);
    const groups = D.newPokemon[tab];
    return `
      <div class="page-head"><h1>Pokémon nuevos del hack</h1><p>${esc(info[2])}</p></div>
      <div class="toolbar"><div class="seg" role="tablist">${NEW_TABS.map((t) => `<button role="tab" data-tab="${t[0]}" aria-pressed="${t[0] === tab}">${t[1]}</button>`).join('')}</div></div>
      ${groups.map((g) => `
        <section class="section">
          ${g.title ? `<h2>${esc(titleCase(g.title))}</h2>` : ''}
          ${g.notes.length ? `<div class="group-notes"><ul>${g.notes.map((n) => `<li>${esc(n)}</li>`).join('')}</ul></div>` : ''}
          <div class="grid grid-2">${g.blocks.map((b) => statCard(b, { spriteName: b.title })).join('')}</div>
        </section>`).join('')}`;
  }

  // ------------------------------------------------------------------
  // Página: movimientos
  // ------------------------------------------------------------------
  function moveCol(side, data, other) {
    const keys = [['type', 'Tipo'], ['power', 'Potencia'], ['acc', 'Precisión'], ['effect', 'Efecto'], ['pp', 'PP']];
    return `
      <div class="move-col ${side}">
        <h4><span>${side === 'hack' ? 'En el hack' : 'Oficial'}</span>${data.type ? typeChip(data.type) : ''}</h4>
        <dl>${keys.filter((k) => k[0] !== 'type').map(([k, l]) => `<dt>${l}</dt><dd class="${side === 'hack' && other[k] !== data[k] ? 'ch' : ''}">${esc(data[k] ?? '—')}</dd>`).join('')}</dl>
      </div>`;
  }

  function pageMoves(q) {
    const f = norm(q.f || '');
    const list = D.moves.filter((m) => !f || norm(m.name).includes(f) || norm(m.hack.type || '').includes(f) || norm(m.official.type || '').includes(f));
    return `
      <div class="page-head"><h1>Movimientos cambiados</h1><p>Potencia, precisión, PP y efecto secundario de cada movimiento retocado. En amarillo, lo que cambia respecto al juego oficial.</p></div>
      <div class="toolbar"><input type="search" id="pageFilter" value="${esc(q.f || '')}" placeholder="Filtrar por nombre o tipo…" aria-label="Filtrar movimientos"><span class="result-count">${list.length} movimientos</span></div>
      <div class="grid grid-moves">${list.map((m) => `<article class="move"><h3>${esc(m.name)}</h3><div class="move-cols">${moveCol('official', m.official, m.hack)}${moveCol('hack', m.hack, m.official)}</div></article>`).join('') || '<div class="empty">Sin resultados.</div>'}</div>`;
  }

  // ------------------------------------------------------------------
  // Página: objetos
  // ------------------------------------------------------------------
  function itemRow(it) {
    return `
      <div class="item">
        <div class="item-head">${it.code ? `<span class="code">${esc(it.code)}</span>` : ''}<b>${esc(it.name)}</b>${stagePill(it.stage)}</div>
        <div class="item-desc">${esc(it.desc)}</div>
        ${it.extra.length ? `<ul class="item-extra">${it.extra.map((x) => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}
      </div>`;
  }

  function pageItems(q) {
    const f = norm(q.f || '');
    const filterItems = (sec) => ({ ...sec, items: sec.items.filter((it) => !f || norm(it.name + ' ' + it.desc + ' ' + (it.code || '') + ' ' + it.extra.join(' ') + ' ' + (it.stage || '')).includes(f)) });
    const locs = D.itemLocations.map(filterItems).filter((s) => s.items.length || (!f && s.note));
    const chg = D.itemChanges.map(filterItems).filter((s) => s.items.length);
    const openAll = !!f;
    const sec = (s, i) => `
      <details class="acc" ${openAll || i === 0 ? 'open' : ''}>
        <summary>${esc(titleCase(s.title))} <span class="n">${s.items.length ? `${s.items.length} objetos` : ''}</span></summary>
        <div class="acc-body">
          ${s.note ? `<p class="acc-note">${esc(s.note)}</p>` : ''}
          ${s.items.length ? `<div class="items">${s.items.map(itemRow).join('')}</div>` : ''}
        </div>
      </details>`;
    return `
      <div class="page-head"><h1>Objetos y MTs</h1><p>Dónde se consigue cada objeto y en qué temporada está disponible por primera vez. La etiqueta de color indica la temporada (T1 Kanto, T2 Archi7, T3 Johto, T4 DLC, T5 Hoenn).</p></div>
      <div class="toolbar"><input type="search" id="pageFilter" value="${esc(q.f || '')}" placeholder="Objeto, MT (p. ej. «MT26»), lugar o temporada…" aria-label="Filtrar objetos"><span class="result-count">${locs.reduce((n, s) => n + s.items.length, 0) + chg.reduce((n, s) => n + s.items.length, 0)} resultados</span></div>
      <section class="section"><h2>Ubicación</h2>${locs.map(sec).join('') || '<div class="empty">Sin resultados.</div>'}</section>
      <section class="section"><h2>Objetos con efecto modificado</h2>${chg.map((s) => sec(s, 0)).join('') || '<div class="empty">Sin resultados.</div>'}</section>`;
  }

  // ------------------------------------------------------------------
  // Página: misiones secundarias (PDF)
  // ------------------------------------------------------------------
  function pageSidequests(q) {
    const f = norm(q.f || '');
    const regions = D.sidequests.map((r) => ({ ...r, quests: r.quests.filter((x) => !f || norm(x.title + ' ' + x.desc + ' ' + x.rewards.join(' ') + ' ' + x.prereq + ' ' + x.bullets.join(' ')).includes(f)) })).filter((r) => r.quests.length);
    const quest = (x) => `
      <article class="quest">
        <h3>${esc(x.title.length > 3 && x.title === x.title.toUpperCase() ? titleCase(x.title) : x.title)}</h3>
        ${x.desc ? `<p>${esc(x.desc)}</p>` : ''}
        ${x.prereq ? `<div class="pre"><b>Requisito:</b> ${esc(x.prereq)}</div>` : ''}
        ${x.bullets.length ? `<ul>${x.bullets.map((b) => `<li>${esc(b)}</li>`).join('')}</ul>` : ''}
        ${x.extra.length ? x.extra.map((e) => `<p class="small" style="margin-top:8px">${esc(e)}</p>`).join('') : ''}
        ${x.rewards.length ? `<div class="lab">Recompensa</div><ul class="rewards">${x.rewards.map((r) => `<li>${esc(r)}</li>`).join('')}</ul>` : ''}
        ${x.video && !/no (está )?disponible/i.test(x.video) ? `<div class="lab">Vídeo tutorial</div><p class="small">${esc(x.video)}</p>` : ''}
      </article>`;
    return `
      <div class="page-head"><h1>Misiones secundarias</h1><p>Cómo activar cada misión, qué necesitas antes y qué te llevas al terminarla. Los equipos de los rivales que aparecen en ellas están en <a href="#/combates">Combates de jefe → Secundarias</a>.</p></div>
      <div class="toolbar"><input type="search" id="pageFilter" value="${esc(q.f || '')}" placeholder="Filtrar por misión, recompensa o lugar…" aria-label="Filtrar misiones"><span class="result-count">${regions.reduce((n, r) => n + r.quests.length, 0)} misiones</span></div>
      ${regions.map((r) => `<section class="section"><h2>${esc(r.name)}</h2><div class="grid grid-2">${r.quests.map(quest).join('')}</div></section>`).join('') || '<div class="empty">Sin resultados.</div>'}`;
  }

  // ------------------------------------------------------------------
  // Página: FAQ y QoL
  // ------------------------------------------------------------------
  function pageFaq() {
    return `
      <div class="page-head"><h1>Preguntas frecuentes</h1><p>${esc(D.faq.intro.join(' '))}</p></div>
      ${D.faq.items.map((it, i) => `
        <details class="faq" ${i === 0 ? 'open' : ''}>
          <summary>${esc(it.q)}</summary>
          <div class="faq-body">${renderLines(it.a)}</div>
        </details>`).join('')}`;
  }

  function renderLines(lines) {
    let html = '', list = null, kv = null;
    const flush = () => { if (list) { html += `<ul>${list.join('')}</ul>`; list = null; } };
    const flushKv = () => { if (kv) { html += `<div class="kv"><b>${esc(kv.k)}</b><span>${esc(kv.v.join(' '))}</span></div>`; kv = null; } };
    lines.forEach((raw) => {
      const s = raw.trim();
      let m;
      if ((m = s.match(/^\|\s*([^:]+):\s*(.*)$/))) {
        flush(); flushKv();
        kv = { k: m[1], v: m[2] ? [m[2]] : [] };
      } else if (s.startsWith('|')) {
        flush(); flushKv();
        kv = { k: s.slice(1).trim(), v: [] };
      } else if (s.startsWith('- ') || s.startsWith('-')) {
        flushKv();
        (list = list || []).push(`<li>${esc(s.replace(/^-\s*/, ''))}</li>`);
      } else if (/^\d+:/.test(s)) {
        flushKv();
        (list = list || []).push(`<li>${esc(s)}</li>`);
      } else if (kv) {
        kv.v.push(s);
      } else {
        flush();
        html += `<p>${esc(s)}</p>`;
      }
    });
    flush(); flushKv();
    return html;
  }

  function pageQol() {
    const secs = D.qol.sections;
    return `
      <div class="page-head"><h1>Farmeo y mecánicas</h1><p>En orden de desbloqueo a lo largo del juego. ${esc(D.qol.notes[1] || '')}</p></div>
      <div class="grid" style="grid-template-columns:1fr">
        ${secs.map((s) => s.heading ? `<h2 style="margin-top:14px">${esc(s.title)}</h2>` : `<article class="qol-card"><h3>${esc(s.title)}</h3>${renderLines(s.lines)}</article>`).join('')}
      </div>`;
  }

  // ------------------------------------------------------------------
  // Búsqueda global
  // ------------------------------------------------------------------
  let INDEX = null;
  function buildIndex() {
    if (INDEX) return INDEX;
    const idx = [];
    D.seasons.forEach((s) => ['main', 'side'].forEach((k) => s[k].forEach((sec, i) => sec.trainers.forEach((t, j) => {
      const pk = [...new Set(Object.values(t.teams).flat().map((p) => p.name))];
      idx.push({ kind: 'Combate', title: titleCase(t.name), where: `T${s.num} ${s.short} · ${titleCase(sec.title)}`, text: norm(t.name + ' ' + sec.title + ' ' + pk.join(' ')), to: `/combates/${s.id}/${k}?f=${encodeURIComponent(t.name)}` });
    }))));
    D.dex.forEach((e) => idx.push({ kind: 'Pokémon', title: e.display, where: e.how ? e.how.slice(0, 110) + (e.how.length > 110 ? '…' : '') : 'No disponible', text: norm(e.display + ' ' + e.how), to: `/pokedex?f=${encodeURIComponent(e.display)}`, spriteInfo: e.sprite }));
    D.itemLocations.forEach((s) => s.items.forEach((it) => idx.push({ kind: it.code ? 'MT' : 'Objeto', title: (it.code ? it.code + ' ' : '') + it.name, where: it.desc, text: norm(it.name + ' ' + (it.code || '') + ' ' + it.desc), to: `/objetos?f=${encodeURIComponent(it.code || it.name)}` })));
    D.moves.forEach((m) => idx.push({ kind: 'Movimiento', title: m.name, where: `${m.official.type || ''} → ${m.hack.type || ''}`, text: norm(m.name), to: `/movimientos?f=${encodeURIComponent(m.name)}` }));
    D.statChanges.forEach((b) => idx.push({ kind: 'Cambio de stats', title: titleCase(b.title), where: (b.abilities || []).join(' / '), text: norm(b.title), to: `/cambios?f=${encodeURIComponent(titleCase(b.title))}`, sprite: titleCase(b.title) }));
    Object.entries(D.newPokemon).forEach(([tab, groups]) => groups.forEach((g) => g.blocks.forEach((b) => idx.push({ kind: 'Pokémon nuevo', title: titleCase(b.title), where: b.type || '', text: norm(b.title), to: `/nuevos/${tab}`, sprite: titleCase(b.title) }))));
    D.sidequests.forEach((r) => r.quests.forEach((x) => idx.push({ kind: 'Secundaria', title: x.title, where: r.name + (x.rewards.length ? ' · ' + x.rewards.join(', ') : ''), text: norm(x.title + ' ' + x.desc + ' ' + x.rewards.join(' ')), to: `/secundarias?f=${encodeURIComponent(x.title)}` })));
    D.faq.items.forEach((it) => idx.push({ kind: 'FAQ', title: it.q, where: it.a[0] || '', text: norm(it.q + ' ' + it.a.join(' ')), to: '/faq' }));
    D.evolutions.changed.concat(D.evolutions.new).forEach((ev) => idx.push({ kind: 'Evolución', title: `${ev.from} → ${ev.to}`, where: ev.method, text: norm(ev.from + ' ' + ev.to + ' ' + ev.method), to: `/evoluciones?f=${encodeURIComponent(ev.from)}`, sprite: ev.to }));
    INDEX = idx;
    return idx;
  }

  function pageSearch(q) {
    const term = norm(q.q || '');
    if (term.length < 2) return `<div class="page-head"><h1>Buscar</h1><p>Escribe al menos dos letras.</p></div>`;
    const words = term.split(/\s+/).filter(Boolean);
    const res = buildIndex().filter((r) => words.every((w) => r.text.includes(w)));
    const rank = (r) => (norm(r.title).startsWith(term) ? 0 : norm(r.title).includes(term) ? 1 : 2);
    res.sort((a, b) => rank(a) - rank(b));
    const hl = (s) => esc(s).replace(new RegExp('(' + words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')', 'gi'), '<mark>$1</mark>');
    return `
      <div class="page-head"><h1>Resultados para «${esc(q.q)}»</h1><p>${res.length} coincidencias.</p></div>
      <div class="results">${res.slice(0, 200).map((r) => `<a class="result" href="#${r.to}">${r.spriteInfo ? spriteFromInfo(r.spriteInfo, 42) : r.sprite ? spriteHTML(r.sprite, 42) : ''}<div><div><b>${hl(r.title)}</b></div><div class="where">${hl(r.where)}</div></div><span class="kind">${r.kind}</span></a>`).join('') || '<div class="empty">Sin resultados.</div>'}</div>`;
  }

  function notFound() {
    return `<div class="empty"><h2>Página no encontrada</h2><p><a href="#/">Volver al inicio</a></p></div>`;
  }

  // ------------------------------------------------------------------
  // Router
  // ------------------------------------------------------------------
  function render(keepScroll) {
    const { parts, q } = parseHash();
    const [p0, p1, p2] = parts;
    let html, wire = null, title = 'Guía Team Rocket Edition';
    switch (p0) {
      case undefined: html = pageHome(); break;
      case 'combates':
        if (!p1) { html = pageBattlesIndex(); title = 'Combates · ' + title; }
        else { html = pageBattles(p1, p2, q); wire = wireBattles; title = `Combates T${p1.slice(1)} · ` + title; }
        break;
      case 'pokedex': html = pageDex(q); wire = wireDex; title = 'Pokémon · ' + title; break;
      case 'evoluciones': html = pageEvolutions(q); wire = wireFilter; title = 'Evoluciones · ' + title; break;
      case 'nuevos': html = pageNew(p1); wire = () => $main.querySelectorAll('[data-tab]').forEach((b) => b.addEventListener('click', () => (location.hash = `/nuevos/${b.dataset.tab}`))); title = 'Nuevos Pokémon · ' + title; break;
      case 'cambios': html = pageStatChanges(q); wire = wireFilter; title = 'Stats · ' + title; break;
      case 'movimientos': html = pageMoves(q); wire = wireFilter; title = 'Movimientos · ' + title; break;
      case 'objetos': html = pageItems(q); wire = wireFilter; title = 'Objetos · ' + title; break;
      case 'secundarias': html = pageSidequests(q); wire = wireFilter; title = 'Secundarias · ' + title; break;
      case 'faq': html = pageFaq(); title = 'FAQ · ' + title; break;
      case 'qol': html = pageQol(); title = 'Farmeo · ' + title; break;
      case 'buscar': html = pageSearch(q); title = 'Buscar · ' + title; break;
      default: html = notFound();
    }
    document.title = title;
    $main.innerHTML = html;
    if (wire) wire();
    renderNav();
    if (!keepScroll) window.scrollTo(0, 0);
    closeSidebar();
  }

  function wireFilter() {
    const inp = document.getElementById('pageFilter');
    if (!inp) return;
    let t;
    inp.addEventListener('input', () => {
      clearTimeout(t);
      t = setTimeout(() => { setQuery({ f: inp.value }); render(true); const el = document.getElementById('pageFilter'); if (el) { el.focus(); el.setSelectionRange(el.value.length, el.value.length); } }, 180);
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
    else document.documentElement.removeAttribute('data-theme');
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', t === 'light' ? '#f4f1f8' : '#16131c');
  }
  let theme = null;
  try { theme = localStorage.getItem('tre-theme'); } catch (e) { /* almacenamiento no disponible */ }
  if (!theme && window.matchMedia('(prefers-color-scheme: light)').matches) theme = 'light';
  applyTheme(theme);
  $themeBtn.addEventListener('click', () => {
    theme = document.documentElement.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
    applyTheme(theme);
    try { localStorage.setItem('tre-theme', theme); } catch (e) { /* ignorar */ }
  });

  let st;
  $search.addEventListener('input', () => {
    clearTimeout(st);
    st = setTimeout(() => {
      const v = $search.value.trim();
      if (v.length >= 2) { history.replaceState(null, '', '#/buscar?q=' + encodeURIComponent(v)); render(true); }
      else if (parseHash().parts[0] === 'buscar') { location.hash = '/'; }
    }, 220);
  });
  $search.addEventListener('keydown', (e) => { if (e.key === 'Enter') { const v = $search.value.trim(); if (v) location.hash = '/buscar?q=' + encodeURIComponent(v); } });

  window.addEventListener('hashchange', () => {
    const { parts, q } = parseHash();
    if (parts[0] === 'buscar') $search.value = q.q || '';
    render();
  });
  render();
})();
