// Floating card preview on hover/focus of .card-ref elements and list rows (§5.5).

import { escapeHtml } from "./mana.js";

const DELAY = 250;
const WIDTH = 260;
const HEIGHT = Math.round(WIDTH * 88 / 63);
const MARGIN = 8;

let timer = null;

function box() {
  return document.getElementById("preview");
}

function finePointer() {
  return window.matchMedia("(hover: hover) and (pointer: fine)").matches;
}

export function hidePreview() {
  clearTimeout(timer);
  timer = null;
  const p = box();
  if (p && !p.hidden) {
    p.hidden = true;
    p.innerHTML = "";
  }
}

function position(p, anchor) {
  const r = anchor.getBoundingClientRect();
  let left = r.right + 12;
  if (left + WIDTH > window.innerWidth - MARGIN) left = r.left - WIDTH - 12;
  left = Math.max(MARGIN, left);
  let top = r.top + r.height / 2 - HEIGHT / 2;
  top = Math.max(MARGIN, Math.min(top, window.innerHeight - HEIGHT - MARGIN));
  p.style.left = `${Math.round(left)}px`;
  p.style.top = `${Math.round(top)}px`;
}

function show(anchor, card) {
  const p = box();
  const src = card.images?.normal || card.images?.large;
  if (!p || !src || !anchor.isConnected) return;
  p.innerHTML = `<img src="${escapeHtml(src)}" alt="${escapeHtml(card.name)}" width="${WIDTH}" decoding="async">`;
  p.hidden = false;
  position(p, anchor);
}

/**
 * Delegated hover/focus preview inside `root`. `resolveCard(name)` returns the card entry
 * for a `data-card` name (or null). Grid tiles are excluded: they enlarge via CSS instead.
 */
export function attachPreview(root, resolveCard) {
  if (!finePointer()) return;
  const target = (e) => e.target?.closest?.(".card-ref, .card-row");

  const start = (e) => {
    const el = target(e);
    if (!el || !root.contains(el)) return;
    if (e.relatedTarget && el.contains(e.relatedTarget)) return; // moving within the same element
    const card = resolveCard(el.dataset.card);
    if (!card) return;
    clearTimeout(timer);
    const anchor = el.classList.contains("card-row") ? (el.querySelector(".card-ref") || el) : el;
    timer = setTimeout(() => show(anchor, card), DELAY);
  };
  const stop = (e) => {
    const el = target(e);
    if (!el) return;
    if (e.relatedTarget && el.contains(e.relatedTarget)) return;
    hidePreview();
  };
  root.addEventListener("mouseover", start);
  root.addEventListener("mouseout", stop);
  root.addEventListener("focusin", start);
  root.addEventListener("focusout", stop);
}

window.addEventListener("scroll", hidePreview, { passive: true, capture: true });
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") hidePreview();
});
