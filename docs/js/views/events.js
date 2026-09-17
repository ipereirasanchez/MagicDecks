// Events: the list (Catalan UI, like the rest of the site) and each event's own pages, which
// are written in the event's languages with a toggle. Card names and text stay in English.

import { t } from "../i18n/ca.js";
import { escapeHtml as esc } from "../components/mana.js";
import { openLightbox } from "../components/lightbox.js";
import { attachPreview } from "../components/preview.js";
import { fillGalleries, prepareRefs } from "./guide.js";

const LANG_KEY = "mtg.eventLang";
const tocMedia = window.matchMedia("(min-width: 900px)");
let tocSync = null;

/** Chrome of the event pages, in every language an event can be written in. */
const L = {
  ca: {
    name: "Català", info: "L'esdeveniment", set: "Guia de l'edició", date: "Data", time: "Horari",
    tbd: "Per confirmar", where: "Lloc", maps: "Obre a Google Maps", edition: "Edició",
    toc: "Contingut", video: "Vídeo de presentació de l'edició", videoOpen: "Obre el vídeo",
    videoFallback: "El navegador no pot reproduir aquest vídeo.",
    cards: "Els noms i el text de les cartes es mantenen en anglès. Passa el ratolí per sobre d'un nom per veure la carta.",
    lang: "Idioma", next: "Continua amb la guia de l'edició", prev: "Torna a l'esdeveniment",
    noSet: "Aquest esdeveniment no té guia de l'edició en aquest idioma.",
  },
  es: {
    name: "Español", info: "El evento", set: "Guía de la edición", date: "Fecha", time: "Horario",
    tbd: "Por confirmar", where: "Lugar", maps: "Abrir en Google Maps", edition: "Edición",
    toc: "Contenido", video: "Vídeo de presentación de la edición", videoOpen: "Abrir el vídeo",
    videoFallback: "El navegador no puede reproducir este vídeo.",
    cards: "Los nombres y el texto de las cartas se mantienen en inglés. Pasa el ratón por encima de un nombre para ver la carta.",
    lang: "Idioma", next: "Seguir con la guía de la edición", prev: "Volver al evento",
    noSet: "Este evento no tiene guía de la edición en este idioma.",
  },
  it: {
    name: "Italiano", info: "L'evento", set: "Guida all'espansione", date: "Data", time: "Orario",
    tbd: "Da confermare", where: "Luogo", maps: "Apri in Google Maps", edition: "Espansione",
    toc: "Contenuti", video: "Video di presentazione dell'espansione", videoOpen: "Apri il video",
    videoFallback: "Il browser non può riprodurre questo video.",
    cards: "I nomi e il testo delle carte restano in inglese. Passa il mouse su un nome per vedere la carta.",
    lang: "Lingua", next: "Continua con la guida all'espansione", prev: "Torna all'evento",
    noSet: "Questo evento non ha una guida all'espansione in questa lingua.",
  },
};

function labels(lang) {
  return L[lang] || L.ca;
}

function readLang() {
  try {
    return localStorage.getItem(LANG_KEY) || "";
  } catch {
    return "";
  }
}

function saveLang(lang) {
  try {
    localStorage.setItem(LANG_KEY, lang);
  } catch {
    /* storage unavailable: the choice just does not persist */
  }
}

/** Pick the language to show: explicit > remembered > the event's default. */
export function pickLang(ev, wanted) {
  const langs = ev.languages || [];
  for (const cand of [wanted, readLang(), ev.default_lang, langs[0]]) {
    if (cand && langs.includes(cand)) return cand;
  }
  return langs[0] || "ca";
}

function fmtDate(iso, lang) {
  if (!iso) return "";
  const d = new Date(`${iso}T12:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  try {
    return new Intl.DateTimeFormat(lang, { weekday: "long", day: "numeric", month: "long", year: "numeric" }).format(d);
  } catch {
    return iso;
  }
}

function eventHref(slug, page = "info", section = null) {
  let h = `#/esdeveniments/${encodeURIComponent(slug)}`;
  if (page === "set") h += "/edicio";
  else if (section) h += "/info";
  if (section) h += `/${encodeURIComponent(section)}`;
  return h;
}

// ---- list ----

function eventCardHtml(ev) {
  const when = fmtDate(ev.date, "ca");
  const meta = [];
  if (ev.set?.name) meta.push(ev.set.name);
  meta.push(ev.time || t("events.tbd"));
  return `
    <a class="deck-card event-card" href="${eventHref(ev.slug)}">
      <span class="deck-art">${ev.art ? `<img src="${esc(ev.art)}" alt="" loading="lazy">` : ""}</span>
      <span class="deck-body">
        <span class="deck-title">${esc(ev.title)}</span>
        <span class="deck-subtitle">${esc([when, ev.location?.name].filter(Boolean).join(" · "))}</span>
        <span class="deck-meta">${meta.map(esc).join('<span class="dot"></span>')}${(ev.languages || [])
          .map((l) => `<span class="badge">${esc(l.toUpperCase())}</span>`).join("")}</span>
      </span>
    </a>`;
}

export function renderEvents(root, index) {
  const events = index.events || [];
  const view = document.createElement("section");
  view.className = "view events";
  view.innerHTML = `
    <header class="page-head">
      <h1>${esc(t("events.title"))}</h1>
      <p class="lead">${esc(t("events.subtitle"))}</p>
    </header>
    ${events.length
      ? `<div class="deck-grid">${events.map(eventCardHtml).join("")}</div>`
      : `<p class="state muted">${esc(t("events.empty"))}</p>`}`;
  root.replaceChildren(view);
}

// ---- event pages ----

function tocHtml(doc, slug, page) {
  const items = [];
  for (const s of doc.sections) {
    const li = { s, children: [] };
    if (s.level === 3 && items.length) items[items.length - 1].children.push(li);
    else items.push(li);
  }
  const link = (s) => `<a href="${eventHref(slug, page, s.id)}">${esc(s.heading)}</a>`;
  return `<ol>${items.map((it) => `<li>${link(it.s)}${it.children.length
    ? `<ol>${it.children.map((c) => `<li>${link(c.s)}</li>`).join("")}</ol>` : ""}</li>`).join("")}</ol>`;
}

function factsHtml(ev, lang) {
  const l = labels(lang);
  const rows = [
    [l.date, ev.date ? esc(fmtDate(ev.date, lang)) : `<span class="tbd">${esc(l.tbd)}</span>`],
    [l.time, ev.time ? esc(ev.time) : `<span class="tbd">${esc(l.tbd)}</span>`],
  ];
  if (ev.location) {
    const name = esc(ev.location.name || l.maps);
    rows.push([l.where, ev.location.url
      ? `<a href="${esc(ev.location.url)}" target="_blank" rel="noopener">${name} ↗</a><span class="small muted"> ${esc(l.maps)}</span>`
      : name]);
  }
  if (ev.set?.name) rows.push([l.edition, `${esc(ev.set.name)} (${esc(String(ev.set.code).toUpperCase())})`]);
  return `<dl class="event-facts">${rows.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${v}</dd></div>`).join("")}</dl>`;
}

function videoHtml(ev, lang) {
  const v = ev.video;
  if (!v?.src) return "";
  const l = labels(lang);
  return `
    <figure class="event-video">
      <video controls preload="metadata" playsinline${ev.art ? ` poster="${esc(ev.art)}"` : ""}>
        <source src="${esc(v.src)}"${v.type ? ` type="${esc(v.type)}"` : ""}>
        ${esc(l.videoFallback)} <a href="${esc(v.src)}" target="_blank" rel="noopener">${esc(l.videoOpen)}</a>
      </video>
      <figcaption>${esc(l.video)}${v.source ? ` · <a href="${esc(v.source)}" target="_blank" rel="noopener">magic.wizards.com ↗</a>` : ""}</figcaption>
    </figure>`;
}

function headerHtml(ev, doc, lang, page) {
  const l = labels(lang);
  const kicker = [ev.set?.name, fmtDate(ev.date, lang)].filter(Boolean).join(" · ");
  return `
    <header class="hero event-head" ${ev.art ? `style="--hero-art:url('${esc(ev.art)}')"` : ""}>
      <div class="hero-bg" aria-hidden="true"></div>
      <div class="hero-content">
        ${kicker ? `<p class="event-kicker">${esc(kicker)}</p>` : ""}
        <h1>${esc(doc?.title || ev.title)}</h1>
        ${doc?.subtitle ? `<p class="hero-subtitle">${esc(doc.subtitle)}</p>` : ""}
        ${ev.languages.length > 1 ? `
        <div class="hero-meta event-langs" role="group" aria-label="${esc(l.lang)}">
          ${ev.languages.map((code) => `<button type="button" class="chip" data-lang="${esc(code)}" aria-pressed="${code === lang}" lang="${esc(code)}">${esc(labels(code).name)}</button>`).join("")}
        </div>` : ""}
        <p class="guide-note">${esc(l.cards)}</p>
      </div>
    </header>
    <nav class="tabs">
      <a class="tab" href="${eventHref(ev.slug)}"${page === "info" ? ' aria-current="page"' : ""}>${esc(l.info)}</a>
      <a class="tab" href="${eventHref(ev.slug, "set")}"${page === "set" ? ' aria-current="page"' : ""}>${esc(l.set)}</a>
    </nav>`;
}

function bodyHtml(doc, ev, lang, page) {
  const l = labels(lang);
  if (!doc) return `<p class="state muted">${esc(l.noSet)}</p>`;
  return `
    <div class="guide-layout">
      <nav class="toc"><details${tocMedia.matches ? " open" : ""}><summary>${esc(l.toc)}</summary>${tocHtml(doc, ev.slug, page)}</details></nav>
      <div class="guide-body md-content" lang="${esc(lang)}">
        ${doc.intro_html}
        ${doc.sections.map((s) => `<section id="${esc(s.id)}"><h${s.level}>${s.heading_html}</h${s.level}>${s.html}</section>`).join("")}
      </div>
    </div>`;
}

/**
 * Render one event page. opts.page = "info" (the event itself) | "set" (the set guide);
 * opts.lang overrides the remembered language; opts.section is scrolled to by the router.
 */
export function renderEvent(root, ev, opts = {}) {
  const page = opts.page === "set" ? "set" : "info";
  const lang = pickLang(ev, opts.lang);
  const l = labels(lang);
  const doc = ev.pages?.[lang]?.[page === "set" ? "set" : "event"] || null;
  const hasSet = ev.languages.some((code) => ev.pages?.[code]?.set);

  const view = document.createElement("article");
  view.className = `view event event-${page}`;
  view.innerHTML = `
    ${headerHtml(ev, doc, lang, page)}
    ${page === "info" ? factsHtml(ev, lang) + videoHtml(ev, lang) : ""}
    ${bodyHtml(doc, ev, lang, page)}
    <p class="event-nav">
      ${page === "set"
        ? `<a class="btn" href="${eventHref(ev.slug)}">← ${esc(l.prev)}</a>`
        : hasSet ? `<a class="btn btn-primary" href="${eventHref(ev.slug, "set")}">${esc(l.next)} →</a>` : ""}
    </p>`;
  if (!hasSet) view.querySelector(".tabs")?.remove();
  root.replaceChildren(view);

  const byName = new Map(Object.entries(ev.cards || {}));
  const ordered = [...byName.values()].sort((a, b) => a.name.localeCompare(b.name));
  const body = view.querySelector(".guide-body");
  let galleries = new Map();
  if (body) {
    body.querySelectorAll(".md-table").forEach((table) => {
      const wrap = document.createElement("div");
      wrap.className = "table-scroll";
      table.replaceWith(wrap);
      wrap.append(table);
    });
    galleries = fillGalleries(body, byName);
    prepareRefs(body, byName);
  }

  const details = view.querySelector(".toc details");
  if (tocSync) tocMedia.removeEventListener("change", tocSync);
  tocSync = details ? (e) => { details.open = e.matches; } : null;
  if (tocSync) tocMedia.addEventListener("change", tocSync);

  view.addEventListener("click", (e) => {
    const langBtn = e.target.closest("button[data-lang]");
    if (langBtn) {
      const next = langBtn.dataset.lang;
      if (next === lang) return;
      saveLang(next);
      const y = window.scrollY;
      renderEvent(root, ev, { page, lang: next });
      window.scrollTo(0, y);
      return;
    }
    const tile = e.target.closest(".card-gallery .card-tile");
    if (tile) {
      openLightbox(galleries.get(tile.closest(".card-gallery")), Number(tile.dataset.index));
      return;
    }
    const ref = e.target.closest(".card-ref");
    if (ref && byName.has(ref.dataset.card)) {
      openLightbox(ordered, ordered.findIndex((c) => c.name === ref.dataset.card));
    }
  });
  view.addEventListener("keydown", (e) => {
    if ((e.key === "Enter" || e.key === " ") && e.target.classList?.contains("card-ref")) {
      e.preventDefault();
      e.target.click();
    }
  });
  attachPreview(view, (name) => byName.get(name) || null);
  return lang;
}
