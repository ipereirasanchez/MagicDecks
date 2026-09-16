// Hash router + page chrome (breadcrumbs, footer, loading / error / not-found states) (§4.2).

import { t } from "./i18n/ca.js";
import { loadIndex, loadDeck, DataError } from "./data.js";
import { renderHome } from "./views/home.js";
import { renderDeck } from "./views/deck.js";
import { renderGuide } from "./views/guide.js";
import { renderLife, disposeLife } from "./views/life.js";
import { closeLightbox } from "./components/lightbox.js";
import { hidePreview } from "./components/preview.js";
import { escapeHtml as esc } from "./components/mana.js";

const app = document.getElementById("app");
const crumbs = document.getElementById("crumbs");

let navToken = 0;     // invalidates renders of routes the user already left
let currentKey = null; // what is on screen, so a guide section change only scrolls

// ---- generic states ----

export function loadingView() {
  return `<div class="state" role="status"><span class="spinner" aria-hidden="true"></span><p>${esc(t("state.loading"))}</p></div>`;
}

export function renderError(root, err, retryFn, what = t("state.error.deck")) {
  root.innerHTML = `
    <div class="state" role="alert">
      <h2>${esc(t("state.error.title"))}</h2>
      <p>${esc(t("state.error.body", { what }))}</p>
      ${err?.message ? `<p class="muted small">${esc(err.message)}</p>` : ""}
      <div class="actions">
        <button type="button" class="btn btn-primary" id="retry">${esc(t("state.retry"))}</button>
        <a class="btn" href="#/">${esc(t("state.home"))}</a>
      </div>
    </div>`;
  root.querySelector("#retry").addEventListener("click", retryFn);
}

export function renderNotFound(root, message = t("state.notfound")) {
  root.innerHTML = `
    <div class="state">
      <h2>${esc(message)}</h2>
      <div class="actions"><a class="btn btn-primary" href="#/">${esc(t("state.home"))}</a></div>
    </div>`;
}

// ---- chrome ----

function setCrumbs(items) {
  const parts = [`<a href="#/">${esc(t("nav.home"))}</a>`];
  for (const it of items) {
    parts.push('<span class="sep" aria-hidden="true">›</span>');
    parts.push(it.href ? `<a href="${it.href}">${esc(it.label)}</a>` : `<span aria-current="page">${esc(it.label)}</span>`);
  }
  crumbs.innerHTML = parts.join("");
}

function scrollToSection(id) {
  const el = id ? document.getElementById(id) : null;
  if (el) el.scrollIntoView();
  else window.scrollTo(0, 0);
}

// ---- routing ----

function parseRoute() {
  const hash = location.hash.replace(/^#/, "") || "/";
  let m;
  if (hash === "/") return { name: "home" };
  if (hash === "/vides") return { name: "life" };
  if ((m = hash.match(/^\/deck\/([^/]+)\/?$/))) return { name: "deck", slug: decodeURIComponent(m[1]), tab: "list" };
  if ((m = hash.match(/^\/deck\/([^/]+)\/stats\/?$/))) return { name: "deck", slug: decodeURIComponent(m[1]), tab: "stats" };
  if ((m = hash.match(/^\/deck\/([^/]+)\/guia(?:\/([^/]+))?\/?$/))) {
    return { name: "guide", slug: decodeURIComponent(m[1]), section: m[2] ? decodeURIComponent(m[2]) : null };
  }
  return { name: "notfound" };
}

async function fetchDeckOrNotFound(slug) {
  try {
    return await loadDeck(slug);
  } catch (err) {
    if (err instanceof DataError && err.status === 404) return null;
    throw err;
  }
}

async function route() {
  const token = ++navToken;
  const r = parseRoute();
  closeLightbox();
  hidePreview();
  disposeLife();

  const key = r.name === "guide" ? `guide:${r.slug}` : r.name === "deck" ? `deck:${r.slug}:${r.tab}` : r.name;
  if (r.name === "guide" && currentKey === key) {
    scrollToSection(r.section); // same guide already on screen: only jump to the section
    return;
  }

  app.innerHTML = loadingView();
  currentKey = null;
  try {
    if (r.name === "life") {
      setCrumbs([{ label: t("nav.life") }]);
      renderLife(app);
      document.title = `${t("life.title")} · ${t("app.title")}`;
      currentKey = key;
      return;
    }
    if (r.name === "home") {
      setCrumbs([]);
      const index = await loadIndex();
      if (token !== navToken) return;
      renderHome(app, index);
      document.title = t("app.title");
    } else if (r.name === "deck" || r.name === "guide") {
      const deck = await fetchDeckOrNotFound(r.slug);
      if (token !== navToken) return;
      if (!deck) {
        setCrumbs([]);
        renderNotFound(app, t("state.deckNotFound"));
        document.title = t("app.title");
        return;
      }
      const deckHref = `#/deck/${encodeURIComponent(deck.slug)}`;
      if (r.name === "deck") {
        renderDeck(app, deck, { tab: r.tab });
        document.title = `${deck.title} · ${t("app.title")}`;
        setCrumbs([{ label: deck.title }]);
      } else if (!deck.guide) {
        renderNotFound(app, t("guide.missing"));
        document.title = `${deck.title} · ${t("app.title")}`;
        setCrumbs([{ label: deck.title, href: deckHref }, { label: t("nav.guide") }]);
        return;
      } else {
        renderGuide(app, deck);
        document.title = `${deck.title} · ${t("nav.guide")}`;
        setCrumbs([{ label: deck.title, href: deckHref }, { label: t("nav.guide") }]);
      }
    } else {
      setCrumbs([]);
      renderNotFound(app, t("state.notfound"));
      document.title = t("app.title");
      return;
    }
    currentKey = key;
    if (r.name === "guide" && r.section) scrollToSection(r.section);
    else window.scrollTo(0, 0);
  } catch (err) {
    if (token !== navToken) return;
    console.error(err);
    setCrumbs([]);
    renderError(app, err, route, r.name === "home" ? t("state.error.index") : t("state.error.deck"));
  }
}

document.querySelector(".brand").textContent = t("app.title");

/* Built here when it is missing, so a cached older index.html cannot break the
   whole script before route() ever runs. */
let lifeLink = document.querySelector("#life-link");
if (!lifeLink) {
  lifeLink = document.createElement("a");
  lifeLink.id = "life-link";
  lifeLink.className = "header-link";
  lifeLink.href = "#/vides";
  document.querySelector(".site-header").append(lifeLink);
}
lifeLink.textContent = t("nav.life");
document.querySelector(".site-footer").innerHTML = `<p>${esc(t("footer.text"))}</p>`;
window.addEventListener("hashchange", route);
route();
