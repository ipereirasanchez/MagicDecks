// Home view: grid of deck cards with an owner filter (§5.1).

import { t } from "../i18n/ca.js";
import { pipsHtml, escapeHtml as esc } from "../components/mana.js";

const OWNER_KEY = "mtg.owner";

/** Selected owner ("" = all). Survives going into a deck and coming back. */
function readOwner() {
  try {
    return sessionStorage.getItem(OWNER_KEY) || "";
  } catch {
    return "";
  }
}

function saveOwner(owner) {
  try {
    if (owner) sessionStorage.setItem(OWNER_KEY, owner);
    else sessionStorage.removeItem(OWNER_KEY);
  } catch {
    /* storage unavailable: the choice just does not persist */
  }
}

function deckCardHtml(d) {
  const meta = [t("home.cards", { n: d.card_count })];
  if (d.bracket != null) meta.push(t("home.bracket", { n: d.bracket }));
  return `
    <a class="deck-card" href="#/deck/${encodeURIComponent(d.slug)}">
      <span class="deck-art">${d.commander.art_crop
        ? `<img src="${esc(d.commander.art_crop)}" alt="${esc(d.commander.name)}" loading="lazy">` : ""}</span>
      <span class="deck-body">
        <span class="deck-title">${esc(d.title)}</span>
        <span class="deck-subtitle">${esc(d.subtitle || d.commander.name)}</span>
        <span class="deck-pips">${pipsHtml(d.color_identity)}</span>
        <span class="deck-meta">${meta.map(esc).join('<span class="dot"></span>')}<span class="badge">${esc(d.owner)}</span></span>
      </span>
    </a>`;
}

function gridHtml(decks) {
  if (!decks.length) return `<p class="state muted">${esc(t("home.empty"))}</p>`;
  return decks.map(deckCardHtml).join("");
}

function filterHtml(owners, decks, current) {
  const chip = (value, label, n, pressed) => `
    <button type="button" class="chip" data-owner="${esc(value)}" aria-pressed="${pressed}">
      ${esc(label)}<span class="chip-count">${n}</span></button>`;
  return `
    <div class="home-filter chip-group" role="group" aria-label="${esc(t("home.filter.owner"))}">
      <span class="chip-group-label">${esc(t("home.filter.owner"))}</span>
      ${chip("", t("home.filter.all"), decks.length, current === "")}
      ${owners.map((o) => chip(o, o, decks.filter((d) => d.owner === o).length, current === o)).join("")}
    </div>`;
}

export function renderHome(root, index) {
  const decks = index.decks || [];
  const owners = (index.owners || []).filter((o) => decks.some((d) => d.owner === o));
  let owner = readOwner();
  if (!owners.includes(owner)) owner = "";

  const view = document.createElement("section");
  view.className = "view home";
  view.innerHTML = `
    <header class="page-head">
      <h1>${esc(t("app.title"))}</h1>
      <p class="lead">${esc(t("home.subtitle"))}</p>
      <a class="btn" href="#/esdeveniments">${esc(t("nav.events"))}</a>
      <a class="btn" href="#/vides">${esc(t("nav.life"))}</a>
    </header>
    ${owners.length ? filterHtml(owners, decks, owner) : ""}
    <div class="deck-grid">${gridHtml(owner ? decks.filter((d) => d.owner === owner) : decks)}</div>`;
  root.replaceChildren(view);

  const group = view.querySelector(".home-filter");
  if (!group) return;
  group.addEventListener("click", (ev) => {
    const btn = ev.target.closest("button[data-owner]");
    if (!btn) return;
    owner = btn.dataset.owner;
    saveOwner(owner);
    group.querySelectorAll("button[data-owner]").forEach((b) => {
      b.setAttribute("aria-pressed", String(b.dataset.owner === owner));
    });
    view.querySelector(".deck-grid").innerHTML =
      gridHtml(owner ? decks.filter((d) => d.owner === owner) : decks);
  });
}
