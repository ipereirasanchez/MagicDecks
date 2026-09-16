// Life counter for playing at the table (§5.7): one seat per player, rotated so
// everybody reads their own panel upright. Big tap zones, commander damage,
// poison, undo, and a screen wake lock.

import { t } from "../i18n/ca.js";
import { loadIndex } from "../data.js";
import { escapeHtml as esc } from "../components/mana.js";

const STORE_KEY = "mtg.life";
const POISON_OUT = 10;
const CMD_OUT = 21;
const MAX_UNDO = 60;
const SEAT_COLORS = ["R", "U", "G", "W", "B", "C"];
const PRESETS = [
  { life: 40, label: "life.preset.commander" },
  { life: 20, label: "life.preset.standard" },
  { life: 30, label: "life.preset.2hg" },
  { life: 25, label: "life.preset.brawl" },
];

/* Grid area + rotation per seat. With 5-6 players the side seats turn 90°, which is
   how people actually sit around a phone in the middle of the table. Rotated seats
   size themselves with container units (see life.css). */
const LAYOUTS = {
  2: { cols: 1, rows: 2, seats: [["1/1/2/2", 180], ["2/1/3/2", 0]] },
  3: { cols: 2, rows: 2, seats: [["1/1/2/2", 180], ["1/2/2/3", 180], ["2/1/3/3", 0]] },
  4: { cols: 2, rows: 2, seats: [["1/1/2/2", 180], ["1/2/2/3", 180], ["2/1/3/2", 0], ["2/2/3/3", 0]] },
  5: { cols: 2, rows: 3, seats: [["1/1/2/2", 90], ["1/2/2/3", -90], ["2/1/3/2", 90], ["2/2/3/3", -90], ["3/1/4/3", 0]] },
  6: { cols: 2, rows: 3, seats: [["1/1/2/2", 90], ["1/2/2/3", -90], ["2/1/3/2", 90], ["2/2/3/3", -90], ["3/1/4/2", 90], ["3/2/4/3", -90]] },
};

let state = null;      // { phase, start, players: [...], awake }
let view = null;       // the <section> we own, or null when not mounted
let wakeLock = null;
const undoStack = [];
const pendingDelta = new Map(); // player id -> { n, timer }
let panelOwner = null;          // whose counters the open panel belongs to
let decks = [];                 // deck index, for picking a commander as the seat avatar

/** The deck list is a nicety: if it cannot be fetched the seats just fall back to colours. */
async function ensureDecks() {
  if (decks.length) return;
  try {
    decks = (await loadIndex()).decks || [];
  } catch {
    decks = [];
  }
}

/** Seat colour from a deck: its own colour when mono, gold when it has several. */
function deckColor(d) {
  const ci = d.color_identity || [];
  if (ci.length === 1) return ci[0];
  if (ci.length > 1) return "M";
  return "C";
}

/** Copy what the seat needs onto the player, so it survives a reload with no network. */
function applyDeck(p, slug, fallbackColor) {
  const d = decks.find((x) => x.slug === slug);
  if (!d) {
    p.deck = null; p.deckArt = null; p.deckName = null; p.color = fallbackColor;
    return;
  }
  p.deck = d.slug;
  p.deckArt = d.commander?.art_crop || null;
  p.deckName = d.commander?.name || d.title;
  p.color = deckColor(d);
}

// ---- state helpers ----

function makePlayers(n, life) {
  return Array.from({ length: n }, (_, i) => ({
    id: i,
    name: t("life.player", { n: i + 1 }),
    color: SEAT_COLORS[i % SEAT_COLORS.length],
    life,
    poison: 0,
    exp: 0,      // experience counters (Meren and friends)
    energy: 0,
    tax: 0,      // times the commander was cast from the command zone
    partners: false,
    deck: null, deckArt: null, deckName: null,
    cmd: {},     // { "<opponent id>:<0|1>": damage } — partners are tracked apart (rule 903.10a)
  }));
}

/** Back to the starting position: life, counters, commander damage and the crown. */
function resetCounters() {
  for (const p of state.players) {
    p.life = state.start;
    p.poison = p.exp = p.energy = p.tax = 0;
    p.cmd = {};
  }
  state.monarch = null;
}

function freshState() {
  return { phase: "setup", start: 40, players: makePlayers(4, 40), awake: true, monarch: null };
}

/** Fill in fields added after a game was stored, so an old save still loads. */
function migrate(s) {
  if (!("monarch" in s)) s.monarch = null;
  for (const p of s.players) {
    for (const [k, v] of Object.entries({ poison: 0, exp: 0, energy: 0, tax: 0 })) {
      if (typeof p[k] !== "number") p[k] = v;
    }
    if (typeof p.partners !== "boolean") p.partners = false;
    if (!("deck" in p)) { p.deck = null; p.deckArt = null; p.deckName = null; }
    if (!p.cmd || typeof p.cmd !== "object") p.cmd = {};
    // pre-partner saves keyed damage by opponent id alone
    for (const key of Object.keys(p.cmd)) {
      if (!key.includes(":")) { p.cmd[`${key}:0`] = p.cmd[key]; delete p.cmd[key]; }
    }
  }
  return s;
}

function load() {
  try {
    const raw = localStorage.getItem(STORE_KEY);
    if (!raw) return null;
    const s = JSON.parse(raw);
    if (!s || !Array.isArray(s.players) || !LAYOUTS[s.players.length]) return null;
    return migrate(s);
  } catch {
    return null; // storage blocked or corrupt: just start fresh
  }
}

function save() {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(state));
  } catch {
    /* storage unavailable: the game simply does not survive a reload */
  }
}

function snapshot() {
  undoStack.push(JSON.stringify({ players: state.players, monarch: state.monarch }));
  if (undoStack.length > MAX_UNDO) undoStack.shift();
}

/** Why a player is out of the game, or null while they are still in. */
function outReason(p) {
  if (p.life <= 0) return t("life.outWhy.life");
  if (p.poison >= POISON_OUT) return t("life.outWhy.poison");
  if (Object.values(p.cmd).some((n) => n >= CMD_OUT)) return t("life.outWhy.cmd");
  return null;
}

function alive() {
  return state.players.filter((p) => !outReason(p));
}

// ---- wake lock ----

async function acquireWake() {
  if (!state?.awake || wakeLock || document.visibilityState !== "visible") return;
  try {
    wakeLock = await navigator.wakeLock?.request("screen");
    wakeLock?.addEventListener?.("release", () => { wakeLock = null; });
  } catch {
    /* not supported, denied, or battery saver: the screen just dims as usual */
  }
}

function releaseWake() {
  try {
    wakeLock?.release();
  } catch { /* already gone */ }
  wakeLock = null;
}

function onVisibility() {
  if (document.visibilityState === "visible") acquireWake();
}

// ---- setup screen ----

/** Decks grouped by owner; empty option keeps the plain colour seat. */
function deckPickerHtml(p, i) {
  if (!decks.length) return "";
  const owners = [...new Set(decks.map((d) => d.owner))];
  return `
    <select data-deck="${p.id}" aria-label="${esc(t("life.deck.label", { n: i + 1 }))}">
      <option value="">${esc(t("life.deck.none"))}</option>
      ${owners.map((o) => `
        <optgroup label="${esc(o)}">
          ${decks.filter((d) => d.owner === o).map((d) => `
            <option value="${esc(d.slug)}"${p.deck === d.slug ? " selected" : ""}>${esc(d.title)}</option>`).join("")}
        </optgroup>`).join("")}
    </select>`;
}

function setupHtml() {
  const counts = [2, 3, 4, 5, 6];
  const chip = (attr, value, label, pressed) =>
    `<button type="button" class="chip" data-${attr}="${esc(value)}" aria-pressed="${pressed}">${esc(label)}</button>`;
  return `
    <header class="page-head">
      <h1>${esc(t("life.title"))}</h1>
      <p class="lead">${esc(t("life.subtitle"))}</p>
    </header>
    <div class="life-setup">
      <div class="chip-group" role="group" aria-label="${esc(t("life.players"))}">
        <span class="chip-group-label">${esc(t("life.players"))}</span>
        ${counts.map((n) => chip("count", n, n, state.players.length === n)).join("")}
      </div>
      <div class="chip-group" role="group" aria-label="${esc(t("life.startLife"))}">
        <span class="chip-group-label">${esc(t("life.startLife"))}</span>
        ${PRESETS.map((p) => chip("start", p.life, `${t(p.label)} · ${p.life}`, state.start === p.life)).join("")}
        <label class="life-custom">
          ${esc(t("life.customLife"))}
          <input type="number" id="life-custom" min="1" max="999" step="1" value="${state.start}"
                 aria-label="${esc(t("life.customLife.label"))}">
        </label>
      </div>
      <ol class="life-names">
        ${state.players.map((p, i) => `
          <li>
            <span class="seat-swatch" data-color="${p.color}" aria-hidden="true"></span>
            <input type="text" data-name="${p.id}" value="${esc(p.name)}" maxlength="18"
                   aria-label="${esc(t("life.name.label", { n: i + 1 }))}">
            ${deckPickerHtml(p, i)}
            <label class="life-partners" title="${esc(t("life.partners.hint"))}">
              <input type="checkbox" data-partners="${p.id}" ${p.partners ? "checked" : ""}>
              ${esc(t("life.partners"))}
            </label>
          </li>`).join("")}
      </ol>
      <label class="life-awake">
        <input type="checkbox" id="life-awake" ${state.awake ? "checked" : ""}>
        ${esc(t("life.keepAwake"))}
      </label>
      <p class="muted small">${esc(t("life.help"))}</p>
      <div class="actions">
        <button type="button" class="btn btn-primary" id="life-start">${esc(t("life.start"))}</button>
        <a class="btn" href="#/">${esc(t("state.home"))}</a>
      </div>
    </div>`;
}

function bindSetup() {
  view.addEventListener("click", (ev) => {
    const btn = ev.target.closest("button[data-count], button[data-start]");
    if (!btn) return;
    if (btn.dataset.count) {
      const n = Number(btn.dataset.count);
      const kept = state.players.slice(0, n);
      state.players = makePlayers(n, state.start).map((p, i) =>
        (kept[i] ? { ...p, name: kept[i].name, partners: kept[i].partners } : p));
    } else {
      state.start = Number(btn.dataset.start);
      state.players.forEach((p) => { p.life = state.start; });
      const box = view.querySelector("#life-custom");
      if (box) box.value = state.start;
    }
    save();
    render();
  });

  view.addEventListener("input", (ev) => {
    const named = ev.target.closest("input[data-name]");
    if (named) {
      const p = state.players[Number(named.dataset.name)];
      if (p) { p.name = named.value; save(); }
      return;
    }
    if (ev.target.id === "life-custom") {
      const n = Math.max(1, Math.min(999, Math.round(Number(ev.target.value) || 0)));
      state.start = n;
      state.players.forEach((p) => { p.life = n; });
      for (const c of view.querySelectorAll("button[data-start]")) {
        c.setAttribute("aria-pressed", String(Number(c.dataset.start) === n));
      }
      save();
    }
  });

  view.addEventListener("change", (ev) => {
    const box = ev.target.closest("input[data-partners]");
    if (box) {
      const p = state.players[Number(box.dataset.partners)];
      if (p) { p.partners = box.checked; save(); }
      return;
    }
    const picker = ev.target.closest("select[data-deck]");
    if (picker) {
      const i = Number(picker.dataset.deck);
      const p = state.players[i];
      if (p) { applyDeck(p, picker.value, SEAT_COLORS[i % SEAT_COLORS.length]); save(); render(); }
    }
  });

  view.querySelector("#life-awake").addEventListener("change", (ev) => {
    state.awake = ev.target.checked;
    save();
    if (state.awake) acquireWake(); else releaseWake();
  });

  view.querySelector("#life-start").addEventListener("click", () => {
    resetCounters();
    state.phase = "table";
    undoStack.length = 0;
    save();
    render();
    acquireWake();
  });
}

// ---- table screen ----

function chipsHtml(p) {
  const reason = outReason(p);
  const cmdTotal = Object.values(p.cmd).reduce((a, b) => a + b, 0);
  const chips = [];
  if (reason) chips.push(`<span class="seat-chip danger">${esc(t("life.out"))} · ${esc(reason)}</span>`);
  if (state.monarch === p.id) chips.push(`<span class="seat-chip" title="${esc(t("life.monarch"))}">👑</span>`);
  if (cmdTotal) chips.push(`<span class="seat-chip" title="${esc(t("life.cmdDamage"))}">⚔ ${cmdTotal}</span>`);
  if (p.poison) chips.push(`<span class="seat-chip${p.poison >= POISON_OUT ? " danger" : ""}" title="${esc(t("life.poison"))}">☠ ${p.poison}</span>`);
  if (p.exp) chips.push(`<span class="seat-chip" title="${esc(t("life.exp"))}">✦ ${p.exp}</span>`);
  if (p.energy) chips.push(`<span class="seat-chip" title="${esc(t("life.energy"))}">⚡ ${p.energy}</span>`);
  if (p.tax) chips.push(`<span class="seat-chip" title="${esc(t("life.tax"))}">⟳ ${p.tax}</span>`);
  return chips.join("");
}

function seatHtml(p, i, layout) {
  const [area, rot] = layout.seats[i];
  const reason = outReason(p);
  return `
    <div class="seat${reason ? " is-out" : ""}" data-seat="${p.id}" data-color="${p.color}"
         style="grid-area:${area}" data-rot="${rot}">
      <div class="seat-inner">
        ${p.deckArt ? `<span class="seat-art" style="background-image:url('${esc(p.deckArt)}')" aria-hidden="true"></span>` : ""}
        <div class="seat-top">
          <span class="seat-name">${esc(p.name)}${p.deckName ? `<span class="seat-deck">${esc(p.deckName)}</span>` : ""}</span>
          <span class="seat-chips">${chipsHtml(p)}</span>
        </div>
        <div class="seat-main">
          <button type="button" class="seat-tap minus" data-step="-1" data-player="${p.id}"
                  aria-label="${esc(t("life.minus", { name: p.name }))}"><span>−</span></button>
          <div class="seat-life">
            <span class="seat-total">${p.life}</span>
            <span class="seat-delta" aria-hidden="true"></span>
          </div>
          <button type="button" class="seat-tap plus" data-step="1" data-player="${p.id}"
                  aria-label="${esc(t("life.plus", { name: p.name }))}"><span>+</span></button>
        </div>
        <button type="button" class="seat-more" data-more="${p.id}">${esc(t("life.counters"))}</button>
      </div>
    </div>`;
}

function panelHtml(p) {
  const row = (label, value, kind, key, danger, note) => `
    <li class="cnt-row${danger ? " danger" : ""}">
      <span class="cnt-label">${esc(label)}${note ? `<span class="cnt-note">${esc(note)}</span>` : ""}</span>
      <button type="button" class="icon-btn" data-adj="${kind}" data-key="${key}" data-d="-1"
              aria-label="${esc(t("life.less", { what: label }))}">−</button>
      <span class="cnt-value">${value}</span>
      <button type="button" class="icon-btn" data-adj="${kind}" data-key="${key}" data-d="1"
              aria-label="${esc(t("life.more", { what: label }))}">+</button>
    </li>`;

  /* One row per opposing commander: with partners each one needs its own 21. */
  const cmdRows = [];
  for (const o of state.players) {
    if (o.id === p.id) continue;
    const slots = o.partners ? [0, 1] : [0];
    for (const which of slots) {
      const key = `${o.id}:${which}`;
      const dealt = p.cmd[key] || 0;
      const label = o.partners ? t("life.cmd.which", { name: o.name, i: which + 1 }) : o.name;
      cmdRows.push(row(label, dealt, "cmd", key, dealt >= CMD_OUT));
    }
  }

  const isMonarch = state.monarch === p.id;
  return `
    <div class="seat-panel" role="dialog" aria-label="${esc(t("life.counters"))}">
      <h2>${esc(p.name)}</h2>
      <ul class="cnt-list">
        ${row(t("life.poison"), p.poison, "poison", "", p.poison >= POISON_OUT, t("life.poison.note"))}
        ${row(t("life.exp"), p.exp, "exp", "")}
        ${row(t("life.energy"), p.energy, "energy", "")}
        ${row(t("life.tax"), p.tax, "tax", "", false, t("life.tax.note", { n: p.tax * 2 }))}
      </ul>
      <button type="button" class="btn${isMonarch ? " btn-primary" : ""}" data-monarch="${p.id}">
        ${esc(isMonarch ? t("life.monarch.drop") : t("life.monarch.make"))}</button>
      ${cmdRows.length ? `
        <h3>${esc(t("life.cmdDamage"))}</h3>
        <ul class="cnt-list">${cmdRows.join("")}</ul>
        <p class="muted small">${esc(t("life.cmdHint"))}</p>` : ""}
      <button type="button" class="btn btn-primary" data-close-panel>${esc(t("life.close"))}</button>
    </div>`;
}

function menuHtml() {
  const last = alive();
  const winner = last.length === 1 && state.players.length > 1 ? last[0] : null;
  return `
    <div class="life-menu" role="dialog" aria-label="${esc(t("life.menu"))}">
      ${winner ? `<p class="life-winner">${esc(t("life.winner", { name: winner.name }))}</p>` : ""}
      <p class="life-roll" id="life-roll" role="status"></p>
      <div class="life-menu-actions">
        <button type="button" class="btn" data-act="undo" ${undoStack.length ? "" : "disabled"}>${esc(t("life.undo"))}</button>
        <button type="button" class="btn" data-act="roll">${esc(t("life.first"))}</button>
        <button type="button" class="btn" data-act="reset">${esc(t("life.reset"))}</button>
        <button type="button" class="btn" data-act="setup">${esc(t("life.newGame"))}</button>
        <a class="btn" href="#/">${esc(t("life.exit"))}</a>
      </div>
      <button type="button" class="btn btn-primary" data-close-panel>${esc(t("life.close"))}</button>
    </div>`;
}

function tableHtml() {
  const layout = LAYOUTS[state.players.length];
  return `
    <div class="life-table" style="--cols:${layout.cols};--rows:${layout.rows}">
      ${state.players.map((p, i) => seatHtml(p, i, layout)).join("")}
      <button type="button" class="life-hub" id="life-hub" aria-label="${esc(t("life.menu"))}">✦</button>
      <div class="life-overlay" id="life-overlay" hidden></div>
    </div>`;
}

// ---- interaction ----

/** Show a running "+3 / -2" next to the total, which fades once the taps stop. */
function flashDelta(id, d) {
  const seat = view.querySelector(`.seat[data-seat="${id}"] .seat-delta`);
  if (!seat) return;
  const cur = pendingDelta.get(id);
  clearTimeout(cur?.timer);
  const n = (cur?.n || 0) + d;
  const timer = setTimeout(() => {
    pendingDelta.delete(id);
    seat.textContent = "";
    seat.classList.remove("on");
  }, 1600);
  pendingDelta.set(id, { n, timer });
  seat.textContent = n > 0 ? `+${n}` : String(n);
  seat.classList.toggle("on", n !== 0);
}

function adjustLife(id, d, { delta = true } = {}) {
  const p = state.players.find((x) => x.id === id);
  if (!p) return;
  p.life += d;
  if (delta) flashDelta(id, d);
  save();
  paintSeat(p);
}

/** Repaint one seat in place: tapping must not rebuild the whole table. */
function paintSeat(p) {
  const seat = view.querySelector(`.seat[data-seat="${p.id}"]`);
  if (!seat) return;
  seat.querySelector(".seat-total").textContent = p.life;
  seat.classList.toggle("is-out", Boolean(outReason(p)));
  seat.querySelector(".seat-chips").innerHTML = chipsHtml(p);
}

/** Tap once, then hold to repeat: slow at first, faster after a couple of seconds. */
function holdToRepeat(el, fn) {
  let delay = null;
  let repeat = null;
  let ticks = 0;
  const stop = () => {
    clearTimeout(delay);
    clearInterval(repeat);
    delay = repeat = null;
    ticks = 0;
    window.removeEventListener("pointerup", stop);
    window.removeEventListener("pointercancel", stop);
  };
  el.addEventListener("pointerdown", (ev) => {
    if (ev.button > 0) return;
    ev.preventDefault();
    stop();
    fn();
    window.addEventListener("pointerup", stop);
    window.addEventListener("pointercancel", stop);
    delay = setTimeout(() => {
      repeat = setInterval(() => {
        fn();
        if (++ticks === 12) { clearInterval(repeat); repeat = setInterval(fn, 60); }
      }, 130);
    }, 420);
  });
  // Keyboard users get the same button without the repeat.
  el.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); fn(); }
  });
}

function openPanel(html) {
  const overlay = view.querySelector("#life-overlay");
  overlay.innerHTML = html;
  overlay.hidden = false;
  overlay.querySelector("button, input, [href]")?.focus();
}

function closePanel() {
  const overlay = view.querySelector("#life-overlay");
  panelOwner = null;
  if (!overlay) return;
  overlay.hidden = true;
  overlay.innerHTML = "";
}

function openSeatPanel(p) {
  panelOwner = p;
  openPanel(panelHtml(p));
}

function adjustCounter(p, kind, key, d) {
  snapshot();
  if (kind === "cmd") {
    const cur = p.cmd[key] || 0;
    const next = Math.max(0, cur + d);
    p.cmd[key] = next;
    if (!next) delete p.cmd[key];
    p.life -= next - cur; // commander damage takes the life with it
  } else {
    p[kind] = Math.max(0, (p[kind] || 0) + d);
  }
  save();
  paintSeat(p);
  openPanel(panelHtml(p)); // repaint in place; it is small and only open on demand
}

/** The crown moves: only one player can be the monarch at a time. */
function setMonarch(id) {
  snapshot();
  const before = state.monarch;
  state.monarch = state.monarch === id ? null : id;
  save();
  for (const p of state.players) if (p.id === before || p.id === state.monarch) paintSeat(p);
  const owner = state.players.find((x) => x.id === id);
  if (owner) openPanel(panelHtml(owner));
}

function rollFirst() {
  const pool = alive();
  const pick = pool[Math.floor(Math.random() * pool.length)];
  const out = view.querySelector("#life-roll");
  if (out && pick) out.textContent = t("life.firstResult", { name: pick.name });
}

function bindTable() {
  for (const el of view.querySelectorAll(".seat-tap")) {
    const id = Number(el.dataset.player);
    const step = Number(el.dataset.step);
    let snapped = false;
    el.addEventListener("pointerdown", () => {
      if (!snapped) { snapshot(); snapped = true; setTimeout(() => { snapped = false; }, 1600); }
    });
    holdToRepeat(el, () => adjustLife(id, step));
  }

  view.addEventListener("click", (ev) => {
    const more = ev.target.closest("[data-more]");
    if (more) {
      const p = state.players.find((x) => x.id === Number(more.dataset.more));
      if (p) openSeatPanel(p);
      return;
    }
    if (ev.target.closest("[data-close-panel]")) { closePanel(); return; }
    if (ev.target.closest("#life-hub")) { openPanel(menuHtml()); return; }

    const crown = ev.target.closest("[data-monarch]");
    if (crown) { setMonarch(Number(crown.dataset.monarch)); return; }

    const adj = ev.target.closest("[data-adj]");
    if (adj) {
      if (panelOwner) adjustCounter(panelOwner, adj.dataset.adj, adj.dataset.key, Number(adj.dataset.d));
      return;
    }

    const act = ev.target.closest("[data-act]")?.dataset.act;
    if (!act) return;
    if (act === "undo" && undoStack.length) {
      const prev = JSON.parse(undoStack.pop());
      state.players = prev.players;
      state.monarch = prev.monarch ?? null;
      save();
      render();
    } else if (act === "roll") {
      rollFirst();
    } else if (act === "reset") {
      snapshot();
      resetCounters();
      save();
      render();
    } else if (act === "setup") {
      state.phase = "setup";
      save();
      render();
    }
  });

  view.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape") closePanel();
  });
}

// ---- mount ----

function render() {
  const wasSetup = state.phase === "setup";
  view.className = `view life${wasSetup ? " life-setup-view" : " life-table-view"}`;
  view.innerHTML = wasSetup ? setupHtml() : tableHtml();
  document.body.classList.toggle("life-fullscreen", !wasSetup);
  if (wasSetup) bindSetup(); else bindTable();
}

export function renderLife(root) {
  state = load() || freshState();
  view = document.createElement("section");
  root.replaceChildren(view);
  render();
  document.addEventListener("visibilitychange", onVisibility);
  if (state.phase === "table") acquireWake();
  // The deck list only decorates the setup screen, so it never blocks the first paint.
  const mounted = view;
  ensureDecks().then(() => {
    if (view === mounted && state.phase === "setup") render();
  });
}

/** Called by the router when leaving the view: drop timers, lock and body class. */
export function disposeLife() {
  if (!view) return;
  for (const { timer } of pendingDelta.values()) clearTimeout(timer);
  pendingDelta.clear();
  document.removeEventListener("visibilitychange", onVisibility);
  document.body.classList.remove("life-fullscreen");
  releaseWake();
  view = null;
}
