// Card lightbox: full-size image + details, keyboard navigation, focus trap (§5.6).

import { t, has } from "../i18n/ca.js";
import { manaHtml, oracleHtml, escapeHtml as esc } from "./mana.js";
import { hidePreview } from "./preview.js";

const eur = new Intl.NumberFormat("ca-ES", { style: "currency", currency: "EUR" });
const FOCUSABLE = 'button:not([disabled]), a[href], [tabindex="0"]';

let state = null; // { cards, index, face, restoreFocus }

function box() {
  return document.getElementById("lightbox");
}

export function isOpen() {
  return state !== null;
}

/** Best image for the lightbox: lossless PNG on large screens, the lighter JPG on phones or with data saver. */
function imageSrc(images) {
  const light = window.innerWidth < 900 || navigator.connection?.saveData;
  return (light ? images?.large : images?.png) || images?.large || images?.png || images?.normal || "";
}

/** Keep assistive tech (and Tab) out of the page behind the dialog. */
function setPageInert(on) {
  for (const el of document.querySelectorAll("#app, .site-header, .site-footer")) el.inert = on;
}

function currentFace(card) {
  if (!card.faces || !card.faces.length) return null;
  return card.faces[state.face % card.faces.length];
}

function preload(offset) {
  const n = state.cards.length;
  const card = state.cards[(state.index + offset + n) % n];
  const src = imageSrc(card.faces ? card.faces[0].images : card.images);
  if (src) new Image().src = src;
}

function detailsHtml(card, face) {
  const name = face ? face.name : card.name;
  const cost = face ? face.mana_cost : card.mana_cost;
  const typeLine = face ? face.type_line : card.type_line;
  const oracle = face ? face.oracle_text : card.oracle_text;
  const power = face ? face.power : card.power;
  const toughness = face ? face.toughness : card.toughness;
  const loyalty = face ? face.loyalty : card.loyalty;

  const rows = [];
  if (power != null || toughness != null) rows.push([t("lightbox.pt"), `${esc(power ?? "")}/${esc(toughness ?? "")}`]);
  if (loyalty != null) rows.push([t("lightbox.loyalty"), esc(loyalty)]);
  rows.push([t("lightbox.set"), `${esc(card.set_name)} (${esc(String(card.set).toUpperCase())}) #${esc(card.collector_number)}`]);
  const rarityKey = `rarity.${card.rarity}`;
  rows.push([t("lightbox.rarity"), esc(has(rarityKey) ? t(rarityKey) : card.rarity)]);
  if (card.artist) rows.push([t("lightbox.artist"), esc(card.artist)]);
  rows.push([t("lightbox.price"), card.price_eur != null ? esc(eur.format(card.price_eur)) : esc(t("lightbox.noprice"))]);
  if (card.qty > 1) rows.push([t("lightbox.qty"), String(card.qty)]);

  return `
    <h2 class="lb-name">${esc(name)}</h2>
    <div class="lb-mana">${manaHtml(cost)}</div>
    <p class="lb-type">${esc(typeLine)}</p>
    <div class="lb-oracle">${oracleHtml(oracle)}</div>
    <dl class="lb-meta">${rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${v}</dd>`).join("")}</dl>
    ${card.scryfall_uri ? `<a class="btn" href="${esc(card.scryfall_uri)}" target="_blank" rel="noopener">${esc(t("lightbox.scryfall"))} ↗</a>` : ""}`;
}

function render(focusSelector) {
  const b = box();
  const { cards, index } = state;
  const card = cards[index];
  const face = currentFace(card);
  const name = face ? face.name : card.name;
  const src = imageSrc(face ? face.images : card.images);
  const multi = cards.length > 1;

  b.innerHTML = `
    <div class="lb-dialog" role="dialog" aria-modal="true" aria-label="${esc(name)}">
      <div class="lb-toolbar">
        <span class="lb-counter">${esc(t("lightbox.counter", { i: index + 1, n: cards.length }))}</span>
        ${card.faces ? `<button type="button" class="btn lb-flip">⟲ ${esc(t("lightbox.flip"))}</button>` : ""}
        <button type="button" class="icon-btn lb-close" aria-label="${esc(t("lightbox.close"))}" title="${esc(t("lightbox.close"))}">×</button>
      </div>
      <div class="lb-body">
        <div class="lb-imgwrap loading">
          ${src ? `<img src="${esc(src)}" alt="${esc(name)}" decoding="async">` : `<div class="tile-placeholder">${esc(name)}</div>`}
        </div>
        <div class="lb-panel">${detailsHtml(card, face)}</div>
      </div>
      ${multi ? `<button type="button" class="icon-btn lb-nav lb-prev" aria-label="${esc(t("lightbox.prev"))}" title="${esc(t("lightbox.prev"))}">‹</button>
                 <button type="button" class="icon-btn lb-nav lb-next" aria-label="${esc(t("lightbox.next"))}" title="${esc(t("lightbox.next"))}">›</button>` : ""}
    </div>`;

  const wrap = b.querySelector(".lb-imgwrap");
  const img = wrap.querySelector("img");
  if (img) {
    const done = () => wrap.classList.remove("loading");
    if (img.complete && img.naturalWidth) done();
    else {
      img.addEventListener("load", done, { once: true });
      img.addEventListener("error", done, { once: true });
    }
  } else {
    wrap.classList.remove("loading");
  }
  b.querySelector(focusSelector)?.focus();
  if (multi) {
    preload(1);
    preload(-1);
  }
}

function go(delta) {
  const n = state.cards.length;
  state.index = (state.index + delta + n) % n;
  state.face = 0;
  render(delta > 0 ? ".lb-next" : ".lb-prev");
}

function trapTab(e) {
  const b = box();
  const items = [...b.querySelectorAll(FOCUSABLE)];
  if (!items.length) return;
  const first = items[0];
  const last = items[items.length - 1];
  const active = document.activeElement;
  const inside = b.contains(active);
  if (e.shiftKey && (active === first || !inside)) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && (active === last || !inside)) {
    e.preventDefault();
    first.focus();
  }
}

function onKey(e) {
  if (!state) return;
  if (e.key === "Escape") {
    e.preventDefault();
    closeLightbox();
  } else if (e.key === "ArrowLeft" && state.cards.length > 1) {
    e.preventDefault();
    go(-1);
  } else if (e.key === "ArrowRight" && state.cards.length > 1) {
    e.preventDefault();
    go(1);
  } else if (e.key === "Tab") {
    trapTab(e);
  }
}

function onClick(e) {
  if (!state) return;
  const b = box();
  if (e.target === b) return closeLightbox(); // backdrop
  if (e.target.closest(".lb-close")) return closeLightbox();
  if (e.target.closest(".lb-prev")) return go(-1);
  if (e.target.closest(".lb-next")) return go(1);
  if (e.target.closest(".lb-flip")) {
    state.face = (state.face + 1) % state.cards[state.index].faces.length;
    render(".lb-flip");
  }
}

/** Open the lightbox on `cards[index]`; the array is the ←/→ navigation context. */
export function openLightbox(cards, index = 0) {
  if (!cards || !cards.length) return;
  const n = cards.length;
  const wasOpen = isOpen();
  state = {
    cards,
    index: ((index % n) + n) % n,
    face: 0,
    restoreFocus: wasOpen ? state.restoreFocus : document.activeElement,
  };
  hidePreview();
  document.body.classList.add("no-scroll");
  setPageInert(true);
  const b = box();
  b.hidden = false;
  if (!wasOpen) {
    document.addEventListener("keydown", onKey);
    b.addEventListener("click", onClick);
  }
  render(".lb-close");
}

export function closeLightbox() {
  if (!state) return;
  const restore = state.restoreFocus;
  state = null;
  const b = box();
  document.removeEventListener("keydown", onKey);
  b.removeEventListener("click", onClick);
  b.hidden = true;
  b.innerHTML = "";
  document.body.classList.remove("no-scroll");
  setPageInert(false);
  if (restore && restore.isConnected && typeof restore.focus === "function") restore.focus();
}
