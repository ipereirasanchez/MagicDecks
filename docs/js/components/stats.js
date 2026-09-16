// Statistics blocks (§5.2 "Stats tab"): pure HTML/CSS bars, one .stat-block per statistic,
// each followed by its pedagogical explanation.

import { pipsHtml, symbolUrl, escapeHtml as esc, COLORS } from "./mana.js";

export const TYPE_ORDER = ["Creature", "Planeswalker", "Battle", "Instant", "Sorcery",
  "Artifact", "Enchantment", "Land", "Other"];

const eur = new Intl.NumberFormat("ca-ES", { style: "currency", currency: "EUR" });
const dec2 = new Intl.NumberFormat("ca-ES", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const COLOR_VAR = { W: "var(--mtg-W)", U: "var(--mtg-U)", B: "var(--mtg-B)", R: "var(--mtg-R)", G: "var(--mtg-G)",
  C: "var(--mtg-C)", multicolor: "var(--mtg-multi)", colorless: "var(--mtg-C)" };
const RARITY_VAR = { common: "var(--rar-common)", uncommon: "var(--rar-uncommon)", rare: "var(--rar-rare)", mythic: "var(--rar-mythic)" };

function symbol(sym, size = 16) {
  return `<img class="ms" src="${symbolUrl(sym)}" alt="{${esc(sym)}}" width="${size}" height="${size}">`;
}

function refHtml(name) {
  return `<span class="card-ref" data-card="${esc(name)}" tabindex="0" role="button">${esc(name)}</span>`;
}

/** Horizontal bars. rows: [{label (html), text (plain, for aria), value, color}]. */
function hbars(rows) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  const aria = rows.map((r) => `${r.text}: ${r.value}`).join(", ");
  return `<div class="hbars" role="img" aria-label="${esc(aria)}">${rows.map((r) => `
    <span class="hbar-label">${r.label}</span>
    <span class="hbar-track"><span class="hbar-fill" style="width:${(r.value / max * 100).toFixed(1)}%;background:${r.color}"></span></span>
    <span class="hbar-value">${r.value}</span>`).join("")}</div>`;
}

function colorRow(c, value, t) {
  return { label: `${symbol(c)} ${esc(t(`color.${c}`))}`, text: t(`color.${c}`), value, color: COLOR_VAR[c] };
}

// ---- one renderer per block ----

function total(s, t) {
  return `<div class="big-number">${s.total_cards}</div>
    <div class="sub-figures"><span><strong>${s.land_count}</strong> ${esc(t("stats.total.lands"))}</span>
    <span><strong>${s.nonland_count}</strong> ${esc(t("stats.total.nonlands"))}</span></div>`;
}

function types(s, t) {
  const rows = TYPE_ORDER.filter((k) => s.by_type[k] > 0)
    .map((k) => ({ label: esc(t(`type.${k}`)), text: t(`type.${k}`), value: s.by_type[k], color: "var(--accent)" }));
  return hbars(rows);
}

function curve(s, t) {
  const keys = ["0", "1", "2", "3", "4", "5", "6", "7+"];
  const max = Math.max(1, ...keys.map((k) => s.mana_curve[k]));
  const aria = keys.map((k) => `${k}: ${s.mana_curve[k]}`).join(", ");
  return `<div class="vbars" role="img" aria-label="${esc(aria)}">${keys.map((k) => `
    <div class="vbar-col"><span class="vbar-value">${s.mana_curve[k]}</span>
      <span class="vbar-track"><span class="vbar-fill" style="height:${(s.mana_curve[k] / max * 100).toFixed(1)}%"></span></span>
      <span class="vbar-label">${esc(k)}</span></div>`).join("")}</div>
    <p class="stat-note">${esc(t("stats.avg.title"))}: <strong>${esc(dec2.format(s.avg_mana_value))}</strong></p>`;
}

function avg(s) {
  return `<div class="big-number">${esc(dec2.format(s.avg_mana_value))}</div>`;
}

function identity(s, t) {
  const names = s.color_identity.length ? s.color_identity.map((c) => t(`color.${c}`)).join(" · ") : t("color.C");
  return `<div class="identity-pips">${pipsHtml(s.color_identity)}<span>${esc(names)}</span></div>`;
}

function pips(s, t) {
  const rows = COLORS.map((c) => colorRow(c, s.pips[c], t));
  if (s.pips.C > 0) rows.push(colorRow("C", s.pips.C, t));
  return hbars(rows) + `<p class="stat-note">${esc(t("color.generic"))}: <strong>${s.pips.generic}</strong></p>`;
}

function colors(s, t) {
  const rows = COLORS.filter((c) => s.cards_by_color[c] > 0).map((c) => colorRow(c, s.cards_by_color[c], t));
  rows.push({ label: esc(t("color.multicolor")), text: t("color.multicolor"), value: s.cards_by_color.multicolor, color: COLOR_VAR.multicolor });
  rows.push({ label: esc(t("color.colorless")), text: t("color.colorless"), value: s.cards_by_color.colorless, color: COLOR_VAR.colorless });
  return hbars(rows);
}

function sources(s, t) {
  const m = s.mana_sources;
  const rows = [...COLORS, "C"].filter((c) => m.by_color[c] > 0).map((c) => colorRow(c, m.by_color[c], t));
  return `<div class="sub-figures" style="margin-bottom:12px">
      <span><strong>${m.lands_total}</strong> ${esc(t("stats.sources.lands"))}</span>
      <span><strong>${m.lands_colored}</strong> ${esc(t("stats.sources.colored"))}</span>
      <span><strong>${m.nonland_producers}</strong> ${esc(t("stats.sources.nonland"))}</span></div>
    ${rows.length ? hbars(rows) : ""}`;
}

function rarity(s, t) {
  const keys = ["common", "uncommon", "rare", "mythic", ...Object.keys(s.rarity).filter((k) => !RARITY_VAR[k])];
  const rows = keys.filter((k) => s.rarity[k] > 0 || RARITY_VAR[k]).map((k) => ({
    label: esc(t(`rarity.${k}`)), text: t(`rarity.${k}`), value: s.rarity[k] || 0, color: RARITY_VAR[k] || "var(--text-muted)",
  }));
  return hbars(rows);
}

function price(s, t) {
  const p = s.price_eur;
  return `<div class="big-number">${esc(eur.format(p.total))}</div>
    <div class="sub-figures"><span>${esc(t("stats.price.priced", { n: p.priced_cards }))}</span><span>${esc(t("stats.price.unpriced", { n: p.unpriced_cards }))}</span></div>
    ${p.most_expensive.length ? `<p class="stat-note"><strong>${esc(t("stats.price.top"))}</strong></p>
      <ul class="ref-list">${p.most_expensive.map((c) => `<li>${refHtml(c.name)}<span class="muted">${esc(eur.format(c.price_eur))}</span></li>`).join("")}</ul>` : ""}`;
}

function keywords(s, t) {
  if (!s.keywords.length) return `<p class="muted">${esc(t("stats.keywords.none"))}</p>`;
  return `<div class="chip-list">${s.keywords.map((k) => `<span class="chip-static">${esc(k.keyword)} ×${k.count}</span>`).join("")}</div>`;
}

function gamechangers(s, t) {
  if (!s.game_changers.length) return `<p class="muted">${esc(t("stats.gamechangers.none"))}</p>`;
  return `<ul class="ref-list">${s.game_changers.map((n) => `<li>${refHtml(n)}</li>`).join("")}</ul>`;
}

const BLOCKS = [["total", total], ["types", types], ["curve", curve], ["avg", avg], ["identity", identity],
  ["pips", pips], ["colors", colors], ["sources", sources], ["rarity", rarity], ["price", price],
  ["keywords", keywords], ["gamechangers", gamechangers]];

/** Render the 12 stat blocks into `container`. Explanations are open on desktop, collapsed on mobile. */
export function renderStats(container, stats, t) {
  const open = window.matchMedia("(min-width: 900px)").matches ? " open" : "";
  container.innerHTML = BLOCKS.map(([key, viz]) => `
    <section class="stat-block stat-${key}">
      <h3>${esc(t(`stats.${key}.title`))}</h3>
      <div class="stat-viz">${viz(stats, t)}</div>
      <details class="stat-help"${open}>
        <summary>${esc(t("stats.help.what"))} · ${esc(t("stats.help.why"))}</summary>
        <p><strong>${esc(t("stats.help.what"))}:</strong> ${esc(t(`stats.${key}.what`))}</p>
        <p><strong>${esc(t("stats.help.why"))}:</strong> ${esc(t(`stats.${key}.why`))}</p>
      </details>
    </section>`).join("");
}
