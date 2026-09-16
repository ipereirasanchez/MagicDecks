// Guide view: header, sticky TOC, build-generated HTML with galleries and card references (§5.3).

import { t } from "../i18n/ca.js";
import { escapeHtml as esc } from "../components/mana.js";
import { openLightbox } from "../components/lightbox.js";
import { attachPreview } from "../components/preview.js";
import { deckOrder } from "./deck.js";

const tocMedia = window.matchMedia("(min-width: 900px)");
let tocSync = null; // current media listener (replaced on every render)

/** bracket_text is markdown: escape it and convert only backticks to <code>. */
export function inlineMd(text) {
  return esc(text).replace(/`([^`]+)`/g, "<code>$1</code>");
}

function tocHtml(deck) {
  const base = `#/deck/${encodeURIComponent(deck.slug)}/guia/`;
  const items = [];
  for (const s of deck.guide.sections) {
    const li = { s, children: [] };
    if (s.level === 3 && items.length) items[items.length - 1].children.push(li);
    else items.push(li);
  }
  const link = (s) => `<a href="${base}${encodeURIComponent(s.id)}">${esc(s.heading)}</a>`;
  return `<ol>${items.map((it) => `<li>${link(it.s)}${it.children.length
    ? `<ol>${it.children.map((c) => `<li>${link(c.s)}</li>`).join("")}</ol>` : ""}</li>`).join("")}</ol>`;
}

function headerHtml(deck) {
  const g = deck.guide;
  const art = deck.commander.images?.art_crop;
  return `
    <header class="hero guide-head" ${art ? `style="--hero-art:url('${esc(art)}')"` : ""}>
      <div class="hero-bg" aria-hidden="true"></div>
      <div class="hero-content">
        <h1>${esc(g.title || deck.title)}</h1>
        ${g.subtitle ? `<p class="hero-subtitle">${esc(g.subtitle)}</p>` : ""}
        ${deck.bracket_text ? `<blockquote class="bracket" lang="ca">${inlineMd(deck.bracket_text)}</blockquote>` : ""}
        <p class="guide-note">${esc(t("guide.language"))}</p>
        <p class="hero-actions"><a class="btn" href="#/deck/${encodeURIComponent(deck.slug)}">← ${esc(t("guide.back"))}</a></p>
      </div>
    </header>`;
}

function galleryTile(card, index) {
  return `<figure class="gallery-item">
    <button type="button" class="card-tile" data-index="${index}">
      <span class="tile-img"><img src="${esc(card.images.normal)}" loading="lazy" alt="${esc(card.name)}"></span>
    </button>
    <figcaption>${esc(card.name)}</figcaption></figure>`;
}

/** Fill every .card-gallery from its data-cards attribute; returns gallery -> cards map. */
function fillGalleries(body, byName) {
  const contexts = new Map();
  body.querySelectorAll(".card-gallery").forEach((el) => {
    const cards = (el.dataset.cards || "").split("|").map((n) => byName.get(n)).filter((c) => c && c.images?.normal);
    el.innerHTML = cards.map(galleryTile).join("");
    contexts.set(el, cards);
  });
  return contexts;
}

function prepareRefs(body, byName) {
  body.querySelectorAll(".card-ref").forEach((el) => {
    if (byName.has(el.dataset.card)) {
      el.setAttribute("tabindex", "0");
      el.setAttribute("role", "button");
    } else {
      el.replaceWith(document.createTextNode(el.textContent));
    }
  });
}

export function renderGuide(root, deck) {
  const g = deck.guide;
  const byName = new Map(deck.cards.map((c) => [c.name, c]));
  const view = document.createElement("article");
  view.className = "view guide";
  view.innerHTML = `
    ${headerHtml(deck)}
    <div class="guide-layout">
      <nav class="toc"><details${tocMedia.matches ? " open" : ""}><summary>${esc(t("guide.toc"))}</summary>${tocHtml(deck)}</details></nav>
      <div class="guide-body md-content" lang="ca">
        ${g.intro_html}
        ${g.sections.map((s) => `<section id="${esc(s.id)}"><h${s.level}>${s.heading_html}</h${s.level}>${s.html}</section>`).join("")}
      </div>
    </div>`;
  root.replaceChildren(view);

  const body = view.querySelector(".guide-body");
  body.querySelectorAll(".md-table").forEach((table) => {
    const wrap = document.createElement("div");
    wrap.className = "table-scroll";
    table.replaceWith(wrap);
    wrap.append(table);
  });
  const galleries = fillGalleries(body, byName);
  prepareRefs(body, byName);

  // The TOC is a collapsible <details> on mobile and always open (summary hidden) on desktop.
  const details = view.querySelector(".toc details");
  if (tocSync) tocMedia.removeEventListener("change", tocSync);
  tocSync = (e) => { details.open = e.matches; };
  tocMedia.addEventListener("change", tocSync);

  view.addEventListener("click", (e) => {
    const tile = e.target.closest(".card-gallery .card-tile");
    if (tile) {
      openLightbox(galleries.get(tile.closest(".card-gallery")), Number(tile.dataset.index));
      return;
    }
    const ref = e.target.closest(".card-ref");
    if (ref && byName.has(ref.dataset.card)) {
      const ordered = deckOrder(deck);
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
}
