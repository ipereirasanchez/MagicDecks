// Deck view: hero, tabs, card list (grid / table with filters) and stats tab (§5.2).

import { t } from "../i18n/ca.js";
import { manaHtml, pipsHtml, symbolUrl, escapeHtml as esc, COLORS } from "../components/mana.js";
import { renderStats, TYPE_ORDER } from "../components/stats.js";
import { openLightbox } from "../components/lightbox.js";
import { attachPreview } from "../components/preview.js";

const eur = new Intl.NumberFormat("ca-ES", { style: "currency", currency: "EUR" });
const VIEW_KEY = "mtg.view";

// Filter state survives tab switches for the same deck and resets when the deck changes.
let state = freshState(null);

function freshState(slug) {
  return { slug, query: "", type: "all", colors: new Set() };
}

function readView() {
  try {
    return localStorage.getItem(VIEW_KEY) === "list" ? "list" : "grid";
  } catch {
    return "grid";
  }
}

function saveView(view) {
  try {
    localStorage.setItem(VIEW_KEY, view);
  } catch {
    /* storage unavailable: the choice just does not persist */
  }
}

function norm(s) {
  return (s || "").normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
}

function sortCards(cards) {
  return [...cards].sort((a, b) => a.cmc - b.cmc || a.name.localeCompare(b.name, "en"));
}

/** Commander group first, then one group per primary type in TYPE_ORDER; sorted by cmc, name. */
export function groupCards(cards) {
  const groups = [];
  const commander = cards.filter((c) => c.is_commander);
  if (commander.length) groups.push({ key: "Commander", cards: sortCards(commander) });
  for (const type of TYPE_ORDER) {
    const list = cards.filter((c) => !c.is_commander && c.primary_type === type);
    if (list.length) groups.push({ key: type, cards: sortCards(list) });
  }
  return groups;
}

/** The whole deck in display order (context for inline card references). */
export function deckOrder(deck) {
  return groupCards(deck.cards).flatMap((g) => g.cards);
}

function applyFilters(deck) {
  const q = norm(state.query.trim());
  const cols = [...state.colors];
  return deck.cards.filter((c) =>
    (!q || norm(c.name).includes(q) || norm(c.full_name).includes(q))
    && (state.type === "all" || c.primary_type === state.type)
    && (!cols.length || cols.some((col) => (col === "C" ? c.colors.length === 0 : c.colors.includes(col)))));
}

function qtySum(cards) {
  return cards.reduce((n, c) => n + c.qty, 0);
}

// ---- HTML builders ----

function heroHtml(deck) {
  const art = deck.commander.images?.art_crop;
  const names = deck.commanders?.length ? deck.commanders : [deck.commander.name];
  const meta = [pipsHtml(deck.stats.color_identity), `<span class="badge">${esc(deck.owner)}</span>`];
  if (deck.bracket != null) meta.push(`<span>${esc(t("home.bracket", { n: deck.bracket }))}</span>`);
  meta.push(`<span>${esc(t("home.cards", { n: deck.stats.total_cards }))}</span>`);
  return `
    <section class="hero" ${art ? `style="--hero-art:url('${esc(art)}')"` : ""}>
      <div class="hero-bg" aria-hidden="true"></div>
      <div class="hero-content">
        <p class="muted" style="color:rgba(255,255,255,.8);margin-bottom:4px">${esc(names.length > 1 ? t("deck.commanders") : t("deck.commander"))}: ${esc(names.join(" + "))}</p>
        <h1>${esc(deck.title)}</h1>
        ${deck.subtitle ? `<p class="hero-subtitle">${esc(deck.subtitle)}</p>` : ""}
        <div class="hero-meta">${meta.join("")}</div>
      </div>
      ${deck.commander.images?.normal ? `<div class="hero-cmd"><img src="${esc(deck.commander.images.normal)}" alt="${esc(deck.commander.name)}" fetchpriority="high"></div>` : ""}
    </section>`;
}

function tabsHtml(deck, tab) {
  const base = `#/deck/${encodeURIComponent(deck.slug)}`;
  const link = (href, label, active) =>
    `<a class="tab" href="${href}"${active ? ' aria-current="page"' : ""}>${esc(label)}</a>`;
  const guide = deck.guide
    ? link(`${base}/guia`, t("deck.tab.guide"), false)
    : `<span class="tab is-disabled" aria-disabled="true" title="${esc(t("guide.missing"))}">${esc(t("deck.tab.guide"))}</span>`;
  return `<nav class="tabs">${link(base, t("deck.tab.list"), tab === "list")}${link(`${base}/stats`, t("deck.tab.stats"), tab === "stats")}${guide}</nav>`;
}

function toolbarHtml(deck, view) {
  const present = TYPE_ORDER.filter((type) => deck.cards.some((c) => c.primary_type === type));
  const chip = (attr, value, label, pressed) =>
    `<button type="button" class="chip${attr === "color" ? " chip-color" : ""}" data-${attr}="${esc(value)}" aria-pressed="${pressed}">${label}</button>`;
  return `
    <div class="toolbar">
      <label class="search"><span class="visually-hidden">${esc(t("deck.search.label"))}</span>
        <input type="search" id="card-search" placeholder="${esc(t("deck.search.placeholder"))}" value="${esc(state.query)}" autocomplete="off"></label>
      <div class="chip-group" role="group" aria-label="${esc(t("deck.filter.type"))}">
        <span class="chip-group-label">${esc(t("deck.filter.type"))}</span>
        ${chip("type", "all", esc(t("deck.filter.all")), state.type === "all")}
        ${present.map((type) => chip("type", type, esc(t(`type.${type}`)), state.type === type)).join("")}
      </div>
      <div class="chip-group" role="group" aria-label="${esc(t("deck.filter.color"))}">
        <span class="chip-group-label">${esc(t("deck.filter.color"))}</span>
        ${[...COLORS, "C"].map((c) => chip("color", c,
          `<img class="ms" src="${symbolUrl(c)}" alt="${esc(t(`color.${c}`))}" width="16" height="16">`, state.colors.has(c))).join("")}
      </div>
      <div class="view-toggle" role="group">
        <button type="button" data-view="grid" aria-pressed="${view === "grid"}">${esc(t("deck.view.grid"))}</button>
        <button type="button" data-view="list" aria-pressed="${view === "list"}">${esc(t("deck.view.list"))}</button>
      </div>
      <span class="results" aria-live="polite"></span>
    </div>`;
}

function tileHtml(card, index) {
  const img = card.images?.normal
    ? `<img src="${esc(card.images.normal)}" loading="lazy" alt="${esc(card.name)}">`
    : `<span class="tile-placeholder">${esc(card.name)}</span>`;
  return `
    <button type="button" class="card-tile" data-index="${index}">
      <span class="tile-img">${img}</span>
      ${card.qty > 1 ? `<span class="qty-badge">×${card.qty}</span>` : ""}
      <span class="tile-name">${esc(card.name)}</span>
    </button>`;
}

function rowHtml(card, index) {
  return `
    <tr class="card-row" data-index="${index}" data-card="${esc(card.name)}">
      <td class="col-qty">${card.qty}</td>
      <td><span class="card-ref" data-card="${esc(card.name)}" data-index="${index}" tabindex="0" role="button">${esc(card.name)}</span></td>
      <td class="col-cost">${manaHtml(card.mana_cost)}</td>
      <td>${esc(card.type_line)}</td>
      <td class="num">${card.price_eur != null ? esc(eur.format(card.price_eur)) : "—"}</td>
    </tr>`;
}

function groupsHtml(groups, view) {
  if (!groups.length) return `<p class="noresults">${esc(t("deck.noresults"))}</p>`;
  let index = 0;
  return groups.map((g) => {
    const title = `<h3 class="group-title">${esc(t(`type.${g.key}`))} <span class="count">(${qtySum(g.cards)})</span></h3>`;
    const items = g.cards.map((c) => (view === "list" ? rowHtml(c, index++) : tileHtml(c, index++))).join("");
    const body = view === "list"
      ? `<div class="table-scroll"><table class="card-table"><thead><tr>
           <th class="col-qty">${esc(t("deck.col.qty"))}</th><th>${esc(t("deck.col.name"))}</th><th>${esc(t("deck.col.cost"))}</th>
           <th>${esc(t("deck.col.type"))}</th><th class="num">${esc(t("deck.col.price"))}</th></tr></thead><tbody>${items}</tbody></table></div>`
      : `<div class="card-grid">${items}</div>`;
    return `<section class="card-group">${title}${body}</section>`;
  }).join("");
}

// ---- list tab ----

function renderList(panel, deck) {
  let view = readView();
  let visible = [];
  panel.innerHTML = `${toolbarHtml(deck, view)}<div class="groups"></div>`;
  const groupsEl = panel.querySelector(".groups");
  const results = panel.querySelector(".results");

  const refresh = () => {
    const groups = groupCards(applyFilters(deck));
    visible = groups.flatMap((g) => g.cards);
    groupsEl.innerHTML = groupsHtml(groups, view);
    results.textContent = t("deck.results", { shown: qtySum(visible), total: deck.stats.total_cards });
  };
  const syncChips = () => {
    panel.querySelectorAll(".chip[data-type]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.type === state.type)));
    panel.querySelectorAll(".chip[data-color]").forEach((b) => b.setAttribute("aria-pressed", String(state.colors.has(b.dataset.color))));
    panel.querySelectorAll("[data-view]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.view === view)));
  };
  refresh();

  panel.querySelector("#card-search").addEventListener("input", (e) => {
    state.query = e.target.value;
    refresh();
  });
  panel.addEventListener("click", (e) => {
    const typeChip = e.target.closest(".chip[data-type]");
    const colorChip = e.target.closest(".chip[data-color]");
    const viewBtn = e.target.closest("[data-view]");
    const tile = e.target.closest(".card-tile[data-index]");
    const ref = e.target.closest(".card-ref[data-index]");
    if (typeChip) {
      state.type = typeChip.dataset.type;
    } else if (colorChip) {
      const c = colorChip.dataset.color;
      if (state.colors.has(c)) state.colors.delete(c); else state.colors.add(c);
    } else if (viewBtn) {
      view = viewBtn.dataset.view;
      saveView(view);
    } else if (tile || ref) {
      openLightbox(visible, Number((tile || ref).dataset.index));
      return;
    } else {
      return;
    }
    syncChips();
    refresh();
  });
}

// ---- view entry point ----

export function renderDeck(root, deck, { tab = "list" } = {}) {
  if (state.slug !== deck.slug) state = freshState(deck.slug);
  const byName = new Map(deck.cards.map((c) => [c.name, c]));
  const view = document.createElement("div");
  view.className = "view deck-view";
  view.innerHTML = `${heroHtml(deck)}${tabsHtml(deck, tab)}<div class="tab-panel${tab === "stats" ? " stats-grid" : ""}"></div>`;
  root.replaceChildren(view);

  const panel = view.querySelector(".tab-panel");
  if (tab === "stats") renderStats(panel, deck.stats, t);
  else renderList(panel, deck);

  // Inline .card-ref without a list index (stats blocks): open on the whole deck at that card.
  view.addEventListener("click", (e) => {
    const ref = e.target.closest(".card-ref:not([data-index])");
    if (!ref || !byName.has(ref.dataset.card)) return;
    const ordered = deckOrder(deck);
    openLightbox(ordered, ordered.findIndex((c) => c.name === ref.dataset.card));
  });
  view.addEventListener("keydown", (e) => {
    if ((e.key === "Enter" || e.key === " ") && e.target.classList?.contains("card-ref")) {
      e.preventDefault();
      e.target.click();
    }
  });
  attachPreview(view, (name) => byName.get(name) || null);
}
