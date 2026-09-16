// Mana / oracle symbol rendering with Scryfall's SVG symbols (§5.8).

export const COLORS = ["W", "U", "B", "R", "G"];

const SYMBOL_BASE = "https://svgs.scryfall.io/card-symbols/";

export function escapeHtml(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

export function symbolUrl(sym) {
  return SYMBOL_BASE + sym.replace(/\//g, "") + ".svg";
}

function symbolImg(sym, cls, size) {
  const alt = escapeHtml(`{${sym}}`);
  return `<img class="${cls}" src="${symbolUrl(sym)}" alt="${alt}" title="${alt}" width="${size}" height="${size}">`;
}

/** "{2}{W}{U} // {X}" -> inline symbol images; "" -> "". */
export function manaHtml(cost) {
  if (!cost) return "";
  const parts = cost.split(" // ").map((part) =>
    part.replace(/\{([^}]+)\}/g, (m, sym) => symbolImg(sym, "ms", 16)));
  return `<span class="mana">${parts.join('<span class="mana-sep">//</span>')}</span>`;
}

/** Large colour pips for a colour identity; an empty identity shows the colourless symbol. */
export function pipsHtml(colors) {
  const list = colors && colors.length ? colors : ["C"];
  return `<span class="pips">${list.map((c) => symbolImg(c, "ms ms-lg", 22)).join("")}</span>`;
}

/** Oracle text: escaped, symbols replaced by images, newlines as <br>. */
export function oracleHtml(text) {
  if (!text) return "";
  return escapeHtml(text)
    .replace(/\{([^}]+)\}/g, (m, sym) => symbolImg(sym, "ms ms-inline", 18))
    .replace(/\n/g, "<br>");
}
