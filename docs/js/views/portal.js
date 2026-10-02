// Portal (`#/`): choose a game, Magic or Pokémon; and the Pokémon game picker (`#/pokemon`).
// Magic keeps its own routes (`#/magic`, `#/deck/…`, `#/esdeveniments`, `#/vides`). Each Pokémon
// game is a self-contained static guide under `docs/pokemon/<game>/`, linked as a plain page.

import { t } from "../i18n/ca.js";
import { escapeHtml as esc } from "../components/mana.js";

const ICON_MAGIC = `<svg viewBox="0 0 64 64" aria-hidden="true"><path d="M32 4 8 18v28l24 14 24-14V18z" fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"/><path d="M32 4v56M8 18l24 14 24-14" fill="none" stroke="currentColor" stroke-width="3" stroke-linejoin="round"/></svg>`;
const ICON_POKEMON = `<svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="26" fill="none" stroke="currentColor" stroke-width="3"/><path d="M6 32h18M40 32h18" stroke="currentColor" stroke-width="3"/><circle cx="32" cy="32" r="8" fill="none" stroke="currentColor" stroke-width="3"/></svg>`;

/** Pokémon games available in the portal. `href` is relative to `docs/`, so it works under a repo subpath. */
export const POKEMON_GAMES = [
  {
    id: "rocket",
    title: "Pokémon Team Rocket Edition",
    subtitle: "TRE 2026 · Dragonsden",
    descKey: "pokemon.rocket.desc",
    href: "pokemon/rocket/",
    lang: "es",
  },
];

function gameCard({ href, icon, title, desc, kicker, note }) {
  return `
    <a class="portal-card" href="${esc(href)}">
      <span class="portal-icon">${icon}</span>
      <span class="portal-body">
        ${kicker ? `<span class="portal-kicker">${esc(kicker)}</span>` : ""}
        <span class="portal-title">${esc(title)}</span>
        <span class="portal-desc">${esc(desc)}</span>
        ${note ? `<span class="portal-note">${esc(note)}</span>` : ""}
      </span>
    </a>`;
}

/** `#/`: the two games side by side. */
export function renderPortal(root, index) {
  const nDecks = (index?.decks || []).length;
  const view = document.createElement("section");
  view.className = "view portal";
  view.innerHTML = `
    <header class="portal-hero">
      <img class="portal-cover" src="img/portada.jpg" srcset="img/portada-small.jpg 900w, img/portada.jpg 1800w"
        sizes="(max-width: 1200px) 100vw, 1200px" alt="${esc(t("portal.cover.alt"))}" fetchpriority="high">
      <div class="portal-hero-text">
        <h1>${esc(t("app.title"))}</h1>
        <p class="lead">${esc(t("portal.subtitle"))}</p>
      </div>
    </header>
    <div class="portal-grid">
      ${gameCard({
        href: "#/magic", icon: ICON_MAGIC, title: t("nav.magic"),
        desc: t("portal.magic.desc"),
        note: nDecks ? t("portal.magic.count", { n: nDecks }) : "",
      })}
      ${gameCard({
        href: "#/pokemon", icon: ICON_POKEMON, title: t("nav.pokemon"),
        desc: t("portal.pokemon.desc"),
        note: t("portal.pokemon.count", { n: POKEMON_GAMES.length }),
      })}
    </div>
    <p class="portal-links">
      <a class="btn" href="#/esdeveniments">${esc(t("nav.events"))}</a>
      <a class="btn" href="#/vides">${esc(t("nav.life"))}</a>
    </p>`;
  root.replaceChildren(view);
}

/** `#/pokemon`: one card per Pokémon game. */
export function renderPokemon(root) {
  const view = document.createElement("section");
  view.className = "view portal";
  view.innerHTML = `
    <header class="page-head">
      <h1>${esc(t("pokemon.title"))}</h1>
      <p class="lead">${esc(t("pokemon.subtitle"))}</p>
    </header>
    <div class="portal-grid">
      ${POKEMON_GAMES.map((g) => gameCard({
        href: g.href, icon: ICON_POKEMON, title: g.title, kicker: g.subtitle,
        desc: t(g.descKey), note: t("pokemon.lang." + g.lang),
      })).join("")}
    </div>`;
  root.replaceChildren(view);
}
