#!/usr/bin/env python3
"""Build the static Commander deck site (see ARCHITECTURE.md).

Reads ``decks/**/*.dek`` (deckstats XML) plus the optional ``.md`` guide next to it and the
Scryfall cache ``decks/_cache/cards.json``; writes ``docs/data/index.json`` and one
``docs/data/decks/<slug>.json`` per deck. Standard library only.
"""
from __future__ import annotations

import html
import json
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DECKS_DIR = ROOT / "decks"
DOCS_DIR = ROOT / "docs"
DATA_DIR = DOCS_DIR / "data"
CACHE_FILE = DECKS_DIR / "_cache" / "cards.json"
OWNERS_FILE = DECKS_DIR / "owners.json"
ROLES_FILE = DECKS_DIR / "roles.json"
ROLES_DIR = DECKS_DIR / "roles"
MARK_START = "<!-- cards:start -->"
MARK_END = "<!-- cards:end -->"
TYPE_ORDER = ["Creature", "Planeswalker", "Battle", "Instant", "Sorcery",
              "Artifact", "Enchantment", "Land", "Other"]
TYPE_PRECEDENCE = ["Land", "Creature", "Planeswalker", "Battle", "Instant",
                   "Sorcery", "Artifact", "Enchantment"]
COLORS = ["W", "U", "B", "R", "G"]
BASIC_LANDS = {"Plains", "Island", "Swamp", "Mountain", "Forest",
               "Snow-Covered Plains", "Snow-Covered Island", "Snow-Covered Swamp",
               "Snow-Covered Mountain", "Snow-Covered Forest", "Wastes"}
DEFAULT_OWNERS = {"default": "Ivan", "decks": {}}
RESERVED_DIRS = {"_cache", "roles", "es", "img"}
IMAGE_KEYS = ("small", "normal", "large", "png", "art_crop")


class BuildError(Exception):
    """Any error that should stop the build with a message."""


class MissingCardError(BuildError):
    """A deck references a card that is not in the Scryfall cache."""


# ---------------------------------------------------------------------------
# 2.1 slugify
# ---------------------------------------------------------------------------

def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name)
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


# ---------------------------------------------------------------------------
# 2.2 .dek parsing
# ---------------------------------------------------------------------------

@dataclass
class DeckEntry:
    name: str
    qty: int
    sideboard: bool


@dataclass
class DeckList:
    commander: str
    cards: list[DeckEntry]
    commanders: list[str] = field(default_factory=list)

    def total(self) -> int:
        return sum(e.qty for e in self.cards)


def parse_dek(path) -> DeckList:
    path = Path(path)
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise BuildError(f"{path.name}: invalid XML ({exc})") from exc
    entries: list[DeckEntry] = []
    by_name: dict[str, DeckEntry] = {}
    commanders: list[str] = []
    for el in root.iter("Cards"):
        name = (el.get("Name") or "").strip()
        if not name:
            continue
        try:
            qty = int(el.get("Quantity", "1"))
        except ValueError as exc:
            raise BuildError(f"{path.name}: bad Quantity for {name!r}") from exc
        if (el.get("Sideboard") or "").lower() == "true" and name not in commanders:
            commanders.append(name)
        if name in by_name:
            by_name[name].qty += qty
        else:
            by_name[name] = DeckEntry(name, qty, False)
            entries.append(by_name[name])
    if not commanders:
        raise BuildError(f'{path.name}: no commander (no <Cards Sideboard="true"> entry)')
    # partners: every Sideboard="true" entry is a commander, in the order of the file
    for i, name in enumerate(commanders):
        cmd = by_name[name]
        cmd.sideboard = True
        entries.remove(cmd)
        entries.insert(i, cmd)
    return DeckList(commanders[0], entries, commanders)


# ---------------------------------------------------------------------------
# 2.3 / 2.4 card helpers
# ---------------------------------------------------------------------------

def primary_type(type_line: str) -> str:
    front = type_line.split(" // ")[0].split(" — ")[0]
    words = front.split()
    for t in TYPE_PRECEDENCE:
        if t in words:
            return t
    return "Other"


def _wubrg(colors) -> list[str]:
    return sorted((c for c in (colors or []) if c in COLORS), key=COLORS.index)


def pick_images(d: dict) -> dict:
    return {k: d.get(k) for k in IMAGE_KEYS}


def _face_summary(face: dict) -> dict:
    return {
        "name": face.get("name", ""),
        "mana_cost": face.get("mana_cost") or "",
        "type_line": face.get("type_line") or "",
        "oracle_text": face.get("oracle_text") or "",
        "power": face.get("power"),
        "toughness": face.get("toughness"),
        "loyalty": face.get("loyalty"),
        "colors": _wubrg(face.get("colors")),
        "images": pick_images(face.get("image_uris") or {}),
    }


def card_summary(obj: dict) -> dict:
    faces_src = obj.get("card_faces") or []
    front = faces_src[0] if faces_src else {}
    colors = obj.get("colors") if "colors" in obj else front.get("colors", [])
    prices = obj.get("prices") or {}
    eur = prices.get("eur")
    type_line = obj.get("type_line") or front.get("type_line") or ""
    faces = None
    if faces_src and faces_src[0].get("image_uris"):
        faces = [_face_summary(f) for f in faces_src]
    return {
        "name": obj["name"],
        "full_name": obj["name"],
        "mana_cost": obj.get("mana_cost") or front.get("mana_cost") or "",
        "cmc": int(obj.get("cmc", 0) or 0),
        "type_line": type_line,
        "primary_type": primary_type(type_line),
        "colors": _wubrg(colors),
        "color_identity": _wubrg(obj.get("color_identity")),
        "produced_mana": list(obj.get("produced_mana") or []),
        "rarity": obj.get("rarity", ""),
        "set": obj.get("set", ""),
        "set_name": obj.get("set_name", ""),
        "collector_number": obj.get("collector_number", ""),
        "oracle_text": obj.get("oracle_text") or front.get("oracle_text") or "",
        "power": obj.get("power", front.get("power")),
        "toughness": obj.get("toughness", front.get("toughness")),
        "loyalty": obj.get("loyalty", front.get("loyalty")),
        "keywords": list(obj.get("keywords") or []),
        "artist": obj.get("artist") or "",
        "layout": obj.get("layout", ""),
        "game_changer": bool(obj.get("game_changer", False)),
        "price_eur": float(eur) if eur is not None else None,
        "images": pick_images(obj.get("image_uris") or front.get("image_uris") or {}),
        "scryfall_uri": obj.get("scryfall_uri", ""),
        "faces": faces,
    }


# ---------------------------------------------------------------------------
# 2.6 card-name matching (mirrors decks/add_images.py)
# ---------------------------------------------------------------------------

def aliases(names: list[str]) -> dict[str, str]:
    """Short name before the comma when unambiguous: 'Vito' -> 'Vito, Thorn of the Dusk Rose'."""
    al: dict[str, str] = {}
    for n in names:
        if ", " not in n:
            continue
        short = n.split(", ")[0]
        clash = [m for m in names if m != n and m.startswith(short)]
        if not clash and short not in al:
            al[short] = n
    return al


def _name_re(name: str) -> re.Pattern:
    return re.compile(r"(?<![\w'])" + re.escape(name) + r"(?![\w])")


def find_names(text: str, names: list[str]) -> list[str]:
    """Full card names cited in text (complete or by alias), in order of first appearance."""
    found: list[tuple[int, str]] = []
    work = text
    for n in sorted(names, key=len, reverse=True):
        pat = _name_re(n)
        m = pat.search(work)
        if m:
            found.append((m.start(), n))
            work = pat.sub(lambda mm: " " * len(mm.group(0)), work)
    for short, n in aliases(names).items():
        if any(n == f for _, f in found):
            continue
        m = _name_re(short).search(work)
        if m:
            found.append((m.start(), n))
    found.sort()
    return [n for _, n in found]


def wrap_card_refs(escaped_text: str, names: list[str]) -> str:
    """Wrap every occurrence of a known name (or alias) in an HTML-escaped text as a .card-ref span."""
    if not names:
        return escaped_text
    holders: list[str] = []
    text = escaped_text

    def wrap(full: str, candidate: str) -> None:
        nonlocal text
        attr = html.escape(full, quote=True)

        def repl(m: re.Match) -> str:
            holders.append(f'<span class="card-ref" data-card="{attr}">{m.group(0)}</span>')
            return f"\x00r{len(holders) - 1}\x00"

        text = _name_re(html.escape(candidate, quote=False)).sub(repl, text)

    for n in sorted(names, key=len, reverse=True):
        wrap(n, n)
    for short, n in aliases(names).items():
        wrap(n, short)
    return re.sub(r"\x00r(\d+)\x00", lambda m: holders[int(m.group(1))], text)


# ---------------------------------------------------------------------------
# 10. card roles (decks/roles.json + decks/roles/<basename>.json)
# ---------------------------------------------------------------------------

def _warn(msg: str) -> None:
    print(f"WARN {msg}", file=sys.stderr)


def load_roles(root: Path | None = None) -> dict:
    """Read decks/roles.json -> {"roles": [{"id", "label", "aliases", "ca"}, ...]} (list order = display order).

    A missing file is tolerated (warning, empty taxonomy); a malformed one is a BuildError.
    """
    root = Path(root) if root is not None else ROOT
    path = root / "decks" / "roles.json"
    if not path.exists():
        _warn(f"{path.name} not found: no role taxonomy")
        return {"roles": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BuildError(f"{path}: invalid JSON ({exc})") from exc
    roles = data.get("roles") if isinstance(data, dict) else None
    if not isinstance(roles, list):
        raise BuildError(f'{path}: expected {{"roles": [...]}}')
    seen: set[str] = set()
    out = []
    for r in roles:
        if not isinstance(r, dict) or not isinstance(r.get("id"), str) or not r["id"]:
            raise BuildError(f"{path}: every role needs a string id")
        if r["id"] in seen:
            raise BuildError(f"{path}: duplicated role id {r['id']!r}")
        seen.add(r["id"])
        aliases_ = r.get("aliases") or []
        if not isinstance(aliases_, list) or not all(isinstance(a, str) for a in aliases_):
            raise BuildError(f"{path}: role {r['id']!r}: aliases must be a list of strings")
        out.append({"id": r["id"], "label": str(r.get("label") or r["id"]),
                    "aliases": list(aliases_), "ca": str(r.get("ca") or "")})
    return {"roles": out}


def load_deck_roles(path, taxonomy: list[dict] | None = None) -> dict[str, list[str]]:
    """Read decks/roles/<basename>.json -> {card name: [role ids]}; {} when the file does not exist.

    When `taxonomy` is given, every id must exist in it (BuildError naming the card and the file).
    """
    path = Path(path)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BuildError(f"{path}: invalid JSON ({exc})") from exc
    cards = data.get("cards") if isinstance(data, dict) else None
    if not isinstance(cards, dict):
        raise BuildError(f'{path}: expected {{"deck": "...", "cards": {{"Card": ["role", ...]}}}}')
    known = {r["id"] for r in taxonomy} if taxonomy else None
    out: dict[str, list[str]] = {}
    for name, ids in cards.items():
        if isinstance(ids, str):
            ids = [ids]
        if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
            raise BuildError(f"{path.name}: roles of {name!r} must be a list of role ids")
        if known is not None:
            for i in ids:
                if i not in known:
                    raise BuildError(f"{path.name}: unknown role {i!r} for card {name!r}")
        out[name] = list(dict.fromkeys(ids))
    return out


def default_roles(card: dict) -> list[str]:
    """Roles of a card that is not classified: lands are 'land', everything else 'utility'."""
    return ["land"] if card.get("primary_type") == "Land" else ["utility"]


_ROLE_PROTECT_RE = re.compile(
    r'<span class="(?:card-ref|role-ref)"[^>]*>.*?</span>|<code>.*?</code>', re.S)


def wrap_role_refs(html_text: str, taxonomy: list[dict] | None) -> str:
    """Wrap every role alias found in the TEXT nodes of an HTML fragment as
    <span class="role-ref" data-role="id">…</span>.

    Aliases are matched longest first, case-insensitively, as whole words
    ((?<![\w-])alias(?![\w-])), never inside a tag, an existing .card-ref/.role-ref span
    or a <code> element.
    """
    if not taxonomy or not html_text:
        return html_text
    pairs = [(a, r["id"]) for r in taxonomy for a in r.get("aliases") or [] if a]
    if not pairs:
        return html_text
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    holders: list[str] = []

    def stash(m: re.Match) -> str:
        holders.append(m.group(0))
        return f"\x00p{len(holders) - 1}\x00"

    text = _ROLE_PROTECT_RE.sub(stash, html_text)
    parts = re.split(r"(<[^>]+>)", text)
    for k in range(0, len(parts), 2):
        seg = parts[k]
        if not seg.strip():
            continue
        for alias, rid in pairs:
            pat = re.compile(r"(?<![\w-])" + re.escape(alias) + r"(?![\w-])", re.I)

            def repl(m: re.Match, rid=rid) -> str:
                holders.append(f'<span class="role-ref" data-role="{html.escape(rid, quote=True)}">'
                               f"{m.group(0)}</span>")
                return f"\x00p{len(holders) - 1}\x00"

            seg = pat.sub(repl, seg)
        parts[k] = seg
    text = "".join(parts)
    return re.sub(r"\x00p(\d+)\x00", lambda m: holders[int(m.group(1))], text)


# ---------------------------------------------------------------------------
# 2.5 Markdown -> HTML
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,6}) (.+)$")
_LIST_RE = re.compile(r"^(\s*)([-*]|\d+\.) (.*)$")
_TABLE_SEP_RE = re.compile(r"^\|?\s*:?-{3,}")
_HR_RE = re.compile(r"^-{3,}$")
_IMG_ALT_RE = re.compile(r'<img\b[^>]*\balt="([^"]*)"', re.I)


@dataclass
class _Block:
    kind: str                  # heading | gallery | raw | blockquote | table | list | para | hr
    src: str                   # source markdown (used for card-name detection)
    level: int = 0             # heading level
    text: str = ""             # heading / blockquote / paragraph text
    names: list = field(default_factory=list)   # gallery card names
    rows: list = field(default_factory=list)    # table rows (first = header)
    lists: list = field(default_factory=list)   # top-level list nodes


def _split_cells(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _build_list_tree(entries: list[tuple[int, str, str]]) -> list[dict]:
    """entries: (indent, marker, text) -> nested list nodes {type, items:[{text, children}]}."""
    top: list[dict] = []
    stack: list[tuple[int, dict]] = []
    for indent, marker, text in entries:
        ltype = "ol" if marker[0].isdigit() else "ul"
        while stack and indent < stack[-1][0]:
            stack.pop()
        if stack and indent < stack[-1][0] + 2 and stack[-1][1]["type"] != ltype:
            stack.pop()  # same level but different marker: sibling list
        if not stack or indent >= stack[-1][0] + 2:
            node = {"type": ltype, "items": []}
            if stack:
                stack[-1][1]["items"][-1]["children"].append(node)
            else:
                top.append(node)
            stack.append((indent, node))
        stack[-1][1]["items"].append({"text": text, "children": []})
    return top


def _is_block_start(line: str) -> bool:
    s = line.strip()
    return (s == MARK_START or line.startswith("<") or line.startswith(">")
            or line.startswith("|") or bool(_HEADING_RE.match(line))
            or bool(_LIST_RE.match(line)) or bool(_HR_RE.match(s)))


def _parse_blocks(lines: list[str]) -> list[_Block]:
    blocks: list[_Block] = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        if not stripped:
            i += 1
            continue
        if stripped == MARK_START:
            j = i + 1
            while j < n and lines[j].strip() != MARK_END:
                j += 1
            chunk = "\n".join(lines[i:j + 1])
            names: list[str] = []
            for alt in _IMG_ALT_RE.findall(chunk):
                alt = html.unescape(alt)
                if alt not in names:
                    names.append(alt)
            if names:
                blocks.append(_Block("gallery", chunk, names=names))
            i = j + 1
            continue
        if line.startswith("<"):
            j = i
            while j < n and lines[j].strip() and lines[j].strip() != MARK_START:
                j += 1
            blocks.append(_Block("raw", "\n".join(lines[i:j])))
            i = j
            continue
        m = _HEADING_RE.match(line)
        if m:
            blocks.append(_Block("heading", line, level=len(m.group(1)), text=m.group(2).strip()))
            i += 1
            continue
        if line.startswith(">"):
            j = i
            while j < n and lines[j].startswith(">"):
                j += 1
            text = "\n".join(re.sub(r"^> ?", "", ln) for ln in lines[i:j])
            blocks.append(_Block("blockquote", "\n".join(lines[i:j]), text=text))
            i = j
            continue
        if _HR_RE.match(stripped):
            blocks.append(_Block("hr", line))
            i += 1
            continue
        if line.startswith("|") and i + 1 < n and _TABLE_SEP_RE.match(lines[i + 1]):
            j = i + 2
            rows = [_split_cells(line)]
            while j < n and lines[j].startswith("|"):
                rows.append(_split_cells(lines[j]))
                j += 1
            blocks.append(_Block("table", "\n".join(lines[i:j]), rows=rows))
            i = j
            continue
        if _LIST_RE.match(line):
            j = i
            entries = []
            while j < n:
                lm = _LIST_RE.match(lines[j])
                if not lm:
                    break
                entries.append((len(lm.group(1)), lm.group(2), lm.group(3)))
                j += 1
            blocks.append(_Block("list", "\n".join(lines[i:j]), lists=_build_list_tree(entries)))
            i = j
            continue
        j = i
        while j < n and lines[j].strip() and not _is_block_start(lines[j]):
            j += 1
        j = max(j, i + 1)
        blocks.append(_Block("para", "\n".join(lines[i:j]),
                             text=" ".join(ln.strip() for ln in lines[i:j])))
        i = j
    return blocks


def _inline(s: str, names: list[str], refs: bool = True) -> str:
    codes: list[str] = []

    def stash(m: re.Match) -> str:
        codes.append(m.group(1))
        return f"\x00{len(codes) - 1}\x00"

    s = re.sub(r"`([^`]+)`", stash, s)
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)([^*]+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"(?<!\w)_(?!\s)([^_]+?)(?<!\s)_(?!\w)", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)",
               lambda m: '<a href="%s" target="_blank" rel="noopener">%s</a>'
               % (m.group(2).replace('"', "&quot;"), m.group(1)), s)
    if refs and names:
        parts = re.split(r"(<[^>]+>)", s)
        s = "".join(wrap_card_refs(p, names) if i % 2 == 0 else p for i, p in enumerate(parts))
    return re.sub(r"\x00(\d+)\x00",
                  lambda m: "<code>" + html.escape(codes[int(m.group(1))], quote=False) + "</code>", s)


def _unique_id(base: str, ids: dict[str, int]) -> str:
    n = ids.get(base, 0) + 1
    ids[base] = n
    return base if n == 1 else f"{base}-{n}"


def _render_list(node: dict, names: list[str]) -> str:
    out = [f"<{node['type']}>"]
    for item in node["items"]:
        out.append("<li>" + _inline(item["text"], names)
                   + "".join(_render_list(c, names) for c in item["children"]) + "</li>")
    out.append(f"</{node['type']}>")
    return "".join(out)


def _render_block(b: _Block, names: list[str], ids: dict[str, int]) -> str:
    if b.kind == "heading":
        hid = _unique_id(slugify(b.text), ids)
        return f'<h{b.level} id="{hid}">{_inline(b.text, names, refs=b.level > 1)}</h{b.level}>'
    if b.kind == "gallery":
        return f'<div class="card-gallery" data-cards="{html.escape("|".join(b.names), quote=True)}"></div>'
    if b.kind == "raw":
        return b.src
    if b.kind == "blockquote":
        return f"<blockquote><p>{_inline(b.text, names)}</p></blockquote>"
    if b.kind == "table":
        head = "".join(f"<th>{_inline(c, names)}</th>" for c in b.rows[0])
        body = "".join("<tr>" + "".join(f"<td>{_inline(c, names)}</td>" for c in row) + "</tr>"
                       for row in b.rows[1:])
        return f'<table class="md-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'
    if b.kind == "list":
        return "".join(_render_list(node, names) for node in b.lists)
    if b.kind == "hr":
        return "<hr>"
    return f"<p>{_inline(b.text, names)}</p>"


def md_to_html(text: str, known_names: list[str] | None = None) -> str:
    names = list(known_names or [])
    ids: dict[str, int] = {}
    return "\n".join(_render_block(b, names, ids) for b in _parse_blocks(text.split("\n")))


# ---------------------------------------------------------------------------
# 2.7 guide parsing
# ---------------------------------------------------------------------------

def _split_title(h1: str) -> tuple[str, str]:
    m = re.match(r"^(.*)\(([^()]*)\)\s*$", h1)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return h1.strip(), ""


def parse_md(text: str, known_names: list[str] | None = None, *,
             taxonomy: list[dict] | None = None) -> dict:
    names = list(known_names or [])
    blocks = _parse_blocks(text.split("\n"))
    h1 = next((b for b in blocks if b.kind == "heading" and b.level == 1), None)
    title, subtitle = _split_title(h1.text) if h1 else ("", "")
    first_section = next((k for k, b in enumerate(blocks)
                          if b.kind == "heading" and b.level in (2, 3)), len(blocks))
    bq = next((b for b in blocks[:first_section] if b.kind == "blockquote"), None)
    bracket_text = bq.text if bq else ""
    m = re.search(r"Bracket\s*(\d)", bracket_text)
    bracket = int(m.group(1)) if m else None

    ids: dict[str, int] = {}
    intro: list[str] = []
    sections: list[dict] = []
    cur: dict | None = None
    for b in blocks:
        if b is h1 or b is bq:
            continue
        if b.kind == "heading" and b.level in (2, 3):
            cur = {"level": b.level, "id": _unique_id(slugify(b.text), ids), "heading": b.text,
                   "heading_html": _inline(b.text, names), "html": [], "gallery": [], "src": [b.text]}
            sections.append(cur)
            continue
        if cur is None:
            if b.kind != "gallery":
                intro.append(_render_block(b, names, ids))
            continue
        cur["html"].append(_render_block(b, names, ids))
        if b.kind == "gallery":
            cur["gallery"].extend(n for n in b.names if n not in cur["gallery"])
        else:
            cur["src"].append(b.src)

    card_refs: list[str] = []
    out_sections = []
    for s in sections:
        cards = find_names("\n".join(s["src"]), names)
        card_refs.extend(c for c in cards if c not in card_refs)
        out_sections.append({"level": s["level"], "id": s["id"], "heading": s["heading"],
                             "heading_html": wrap_role_refs(s["heading_html"], taxonomy),
                             "html": wrap_role_refs("\n".join(s["html"]), taxonomy),
                             "gallery": s["gallery"], "cards": cards})
    return {"title": title, "subtitle": subtitle, "bracket": bracket, "bracket_text": bracket_text,
            "intro_html": wrap_role_refs("\n".join(intro), taxonomy),
            "sections": out_sections, "card_refs": card_refs}


# ---------------------------------------------------------------------------
# 2.8 statistics
# ---------------------------------------------------------------------------

def compute_stats(cards: list[dict], commander_name: str, taxonomy: list[dict] | None = None) -> dict:
    nonland = [c for c in cards if c["primary_type"] != "Land"]
    lands = [c for c in cards if c["primary_type"] == "Land"]
    total = sum(c["qty"] for c in cards)

    by_type = {t: 0 for t in TYPE_ORDER}
    for c in cards:
        by_type[c["primary_type"]] += c["qty"]

    curve = {k: 0 for k in ["0", "1", "2", "3", "4", "5", "6", "7+"]}
    for c in nonland:
        b = min(c["cmc"], 7)
        curve["7+" if b == 7 else str(b)] += c["qty"]
    nonland_qty = sum(c["qty"] for c in nonland)
    avg = round(sum(c["cmc"] * c["qty"] for c in nonland) / nonland_qty, 2) if nonland_qty else 0.0

    pips = {c: 0 for c in COLORS}
    pips["C"] = 0
    generic = 0
    for c in nonland:
        cost = c["mana_cost"].split(" // ")[0]
        for sym in re.findall(r"\{([^}]+)\}", cost):
            if sym in COLORS or sym == "C":
                pips[sym] += c["qty"]
            elif sym.isdigit():
                generic += int(sym) * c["qty"]
            elif "/" in sym:
                for part in sym.split("/"):
                    if part in COLORS:
                        pips[part] += c["qty"]
    pips["generic"] = generic

    identity: set[str] = set()
    for c in cards:
        identity.update(c["color_identity"])

    by_color = {c: 0 for c in COLORS}
    by_color.update({"multicolor": 0, "colorless": 0})
    for c in nonland:
        cols = c["colors"]
        key = "colorless" if not cols else cols[0] if len(cols) == 1 else "multicolor"
        by_color[key] += c["qty"]

    src_color = {c: 0 for c in COLORS + ["C"]}
    for c in cards:
        for p in c.get("produced_mana") or []:
            if p in src_color:
                src_color[p] += c["qty"]
    sources = {
        "lands_total": sum(c["qty"] for c in lands),
        "lands_colored": sum(c["qty"] for c in lands
                             if any(p in COLORS for p in c.get("produced_mana") or [])),
        "nonland_producers": sum(c["qty"] for c in nonland if c.get("produced_mana")),
        "by_color": src_color,
    }

    rarity = {"common": 0, "uncommon": 0, "rare": 0, "mythic": 0}
    for c in cards:
        rarity[c["rarity"]] = rarity.get(c["rarity"], 0) + c["qty"]

    priced = [c for c in cards if c["price_eur"] is not None]
    top = sorted(priced, key=lambda c: (-c["price_eur"], c["name"]))[:5]
    price = {
        "total": round(sum(c["price_eur"] * c["qty"] for c in priced), 2),
        "priced_cards": sum(c["qty"] for c in priced),
        "unpriced_cards": sum(c["qty"] for c in cards if c["price_eur"] is None),
        "most_expensive": [{"name": c["name"], "price_eur": c["price_eur"]} for c in top],
    }

    kw_count: dict[str, int] = {}
    for c in cards:
        for kw in c.get("keywords") or []:
            kw_count[kw] = kw_count.get(kw, 0) + c["qty"]
    keywords = [{"keyword": k, "count": v}
                for k, v in sorted(kw_count.items(), key=lambda kv: (-kv[1], kv[0]))[:10]]

    roles = []
    for r in taxonomy or []:
        members = [c for c in cards if r["id"] in (c.get("roles") or [])]
        roles.append({"id": r["id"], "count": sum(c["qty"] for c in members),
                      "cards": [c["name"] for c in members]})

    return {
        "total_cards": total,
        "distinct_cards": len(cards),
        "land_count": sources["lands_total"],
        "nonland_count": nonland_qty,
        "by_type": by_type,
        "mana_curve": curve,
        "avg_mana_value": avg,
        "color_identity": _wubrg(identity),
        "pips": pips,
        "cards_by_color": by_color,
        "mana_sources": sources,
        "rarity": rarity,
        "price_eur": price,
        "keywords": keywords,
        "game_changers": sorted(c["name"] for c in cards if c.get("game_changer")),
        "roles": roles,
    }


# ---------------------------------------------------------------------------
# 2.9 / 2.10 deck and site build
# ---------------------------------------------------------------------------

def find_deks(decks_dir) -> list[Path]:
    """Every .dek under decks/: the loose ones plus the ones in an owner folder
    (decks/<Owner>/*.dek). Reserved folders (_cache, roles, es, img) are skipped."""
    decks_dir = Path(decks_dir)
    deks = list(decks_dir.glob("*.dek"))
    for sub in decks_dir.iterdir():
        if not sub.is_dir() or sub.name in RESERVED_DIRS or sub.name.startswith("."):
            continue
        deks += sub.glob("*.dek")
    return sorted(deks, key=lambda p: (p.parent.name.casefold(), p.name.casefold()))


def deck_owner(dek_path, owners: dict, decks_dir=None) -> str:
    """owners.json entry > owner folder name (decks/<Owner>/x.dek) > owners.json default."""
    dek_path = Path(dek_path)
    explicit = owners.get("decks", {}).get(dek_path.stem)
    if explicit:
        return explicit
    parent = dek_path.parent
    if decks_dir is not None and parent != Path(decks_dir) and parent.name not in RESERVED_DIRS:
        return parent.name
    return owners.get("default", DEFAULT_OWNERS["default"])


def build_deck(dek_path, md_path, cards_cache: dict, owners: dict,
               taxonomy: list[dict] | None = None, roles_path=None, decks_dir=None) -> dict:
    """Build the §3.2 deck object. `taxonomy` = load_roles(...)["roles"]; `roles_path` defaults to
    roles/<basename>.json next to the .dek and, if there is none, decks/roles/<basename>.json
    (missing -> every card gets a default role). `decks_dir` enables the owner-folder rule."""
    dek_path = Path(dek_path)
    basename = dek_path.stem
    slug = slugify(basename)
    deck = parse_dek(dek_path)
    if roles_path is None:
        roles_path = dek_path.parent / "roles" / f"{basename}.json"
        if not Path(roles_path).exists() and decks_dir is not None:
            roles_path = Path(decks_dir) / "roles" / f"{basename}.json"
    deck_roles = load_deck_roles(roles_path, taxonomy)
    cards = []
    missing_roles = 0
    for entry in deck.cards:
        obj = cards_cache.get(entry.name)
        if obj is None:
            raise MissingCardError(f"card {entry.name!r} not found in cache (deck {dek_path.name})")
        card = card_summary(obj)
        card["name"] = entry.name
        card["qty"] = entry.qty
        card["is_commander"] = entry.sideboard
        if deck_roles.get(entry.name):
            card["roles"] = deck_roles[entry.name]
        else:
            card["roles"] = default_roles(card)
            missing_roles += 1
        cards.append(card)
    if missing_roles:
        _warn(f"{slug}: {missing_roles} cards without roles")
    extra = [n for n in deck_roles if n not in {c["name"] for c in cards}]
    if extra:
        _warn(f"{slug}: {len(extra)} roles entries not in deck ({', '.join(extra[:5])})")

    title = " ".join(basename.replace("_", " ").split())
    subtitle, bracket, bracket_text, guide = "", None, "", None
    if md_path is not None:
        md_path = Path(md_path)
        known = [e.name for e in deck.cards if e.name not in BASIC_LANDS]
        guide = parse_md(md_path.read_text(encoding="utf-8"), known, taxonomy=taxonomy)
        title = guide["title"] or title
        subtitle, bracket, bracket_text = guide["subtitle"], guide["bracket"], guide["bracket_text"]

    return {
        "slug": slug,
        "dek_file": dek_path.name,
        "md_file": md_path.name if md_path is not None else None,
        "title": title,
        "subtitle": subtitle,
        "owner": deck_owner(dek_path, owners, decks_dir),
        "bracket": bracket,
        "bracket_text": bracket_text,
        "commander": cards[0],
        "commanders": [c["name"] for c in cards if c["is_commander"]],
        "cards": cards,
        "stats": compute_stats(cards, deck.commander, taxonomy),
        "guide": guide,
    }


def build_index(decks: list[dict], taxonomy: list[dict] | None = None) -> dict:
    entries = []
    for d in decks:
        imgs = d["commander"]["images"]
        entries.append({
            "slug": d["slug"],
            "title": d["title"],
            "subtitle": d["subtitle"],
            "owner": d["owner"],
            "bracket": d["bracket"],
            "card_count": d["stats"]["total_cards"],
            "color_identity": d["stats"]["color_identity"],
            "commander": {"name": d["commander"]["name"], "art_crop": imgs.get("art_crop"),
                          "normal": imgs.get("normal")},
            "commanders": d.get("commanders") or [d["commander"]["name"]],
            "has_guide": d["guide"] is not None,
            "price_eur": d["stats"]["price_eur"]["total"],
            "file": f"data/decks/{d['slug']}.json",
        })
    entries.sort(key=lambda e: e["title"].casefold())
    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "owners": sorted({d["owner"] for d in decks}),
        "decks": entries,
        "roles": [{"id": r["id"], "label": r["label"], "ca": r["ca"]} for r in taxonomy or []],
    }


def _load_owners(path: Path) -> dict:
    if not path.exists():
        path.write_text(json.dumps(DEFAULT_OWNERS, indent=2) + "\n", encoding="utf-8")
        return json.loads(json.dumps(DEFAULT_OWNERS))
    try:
        owners = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BuildError(f"{path}: invalid JSON ({exc})") from exc
    if not isinstance(owners, dict) or not isinstance(owners.get("default"), str) \
            or not isinstance(owners.get("decks"), dict):
        raise BuildError(f'{path}: expected {{"default": "...", "decks": {{...}}}}')
    return owners


def _write_json(path: Path, obj) -> None:
    with path.open("w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")


def build_all(root: Path | None = None) -> dict:
    root = Path(root) if root is not None else ROOT
    decks_dir = root / "decks"
    cache_file = decks_dir / "_cache" / "cards.json"
    docs_dir = root / "docs"
    decks_out = docs_dir / "data" / "decks"
    if not cache_file.exists():
        raise BuildError(f"missing Scryfall cache {cache_file}")
    try:
        cache = json.loads(cache_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BuildError(f"{cache_file}: invalid JSON ({exc})") from exc
    owners = _load_owners(decks_dir / "owners.json")
    taxonomy = load_roles(root)["roles"]

    decks_out.mkdir(parents=True, exist_ok=True)
    (docs_dir / ".nojekyll").touch()
    decks: list[dict] = []
    written: set[Path] = set()
    for dek in find_deks(decks_dir):
        md = dek.with_suffix(".md")
        deck = build_deck(dek, md if md.exists() else None, cache, owners, taxonomy,
                          decks_dir=decks_dir)
        if any(d["slug"] == deck["slug"] for d in decks):
            raise BuildError(f"slug collision: {deck['slug']} ({dek.name})")
        out = decks_out / f"{deck['slug']}.json"
        _write_json(out, deck)
        written.add(out)
        decks.append(deck)
        print(f"OK {deck['slug']} {deck['stats']['total_cards']} cards")
    for stale in decks_out.glob("*.json"):
        if stale not in written:
            stale.unlink()
    index = build_index(decks, taxonomy)
    _write_json(docs_dir / "data" / "index.json", index)
    return index


def main() -> None:
    try:
        build_all()
    except BuildError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
