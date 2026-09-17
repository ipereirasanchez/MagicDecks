"""Unit tests for tools/build_site.py — implements the test plan of ARCHITECTURE.md §7.

Run from the repository root:  python3 -m unittest discover -s tests -v
"""
import contextlib
import html
import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import build_site  # noqa: E402

DECKS = ROOT / "decks"
IVAN = DECKS / "Ivan"          # decks are stored per owner: decks/<Owner>/<name>.dek
MIQUEL = DECKS / "Miquel"
CACHE_FILE = DECKS / "_cache" / "cards.json"

DEK_SLUGS = {
    "Ms_Bumbleflower": "ms-bumbleflower",
    "Edgar_Markov_-_Vampire_Tribal": "edgar-markov-vampire-tribal",
    "Krenko_Mob_Boss_Goblin_Combos": "krenko-mob-boss-goblin-combos",
    "_Meren_of_Clan_Nel_Toth_EAT_PRAY_KILL": "meren-of-clan-nel-toth-eat-pray-kill",
    "Sauron_the_Dark_Lord_": "sauron-the-dark-lord",
    "Hobbits": "hobbits",
}

CARD_KEYS = {
    "name", "full_name", "mana_cost", "cmc", "type_line", "primary_type", "colors",
    "color_identity", "produced_mana", "rarity", "set", "set_name", "collector_number",
    "oracle_text", "power", "toughness", "loyalty", "keywords", "artist", "layout",
    "game_changer", "price_eur", "images", "scryfall_uri", "faces",
}

STATS_KEYS = {
    "total_cards", "distinct_cards", "land_count", "nonland_count", "by_type", "mana_curve",
    "avg_mana_value", "color_identity", "pips", "cards_by_color", "mana_sources", "rarity",
    "price_eur", "keywords", "game_changers", "roles",
}

INDEX_DECK_KEYS = {
    "slug", "title", "subtitle", "owner", "bracket", "card_count", "color_identity",
    "commander", "commanders", "has_guide", "price_eur", "file",
}

DEFAULT_OWNERS = {"default": "Ivan", "decks": {}}

# every list is a legal 100-card Commander deck except Hobbits, whose proxy sheet still
# carries the 8 upgrade cards that have to replace 8 of the old ones
DECK_TOTALS = {b: 100 for b in DEK_SLUGS}
DECK_TOTALS["Hobbits"] = 108


# ----------------------------------------------------------------------------- helpers

def dek_xml(entries, commander=None):
    """Build a .dek document. entries = [(raw_name, qty)], raw_name is XML-escaped already."""
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<Deck>", "  <NetDeckID>0</NetDeckID>",
             "  <PreconstructedDeckID>0</PreconstructedDeckID>"]
    for name, qty in entries:
        lines.append('  <Cards CatID="0" Quantity="%d" Sideboard="false" Name="%s" />' % (qty, name))
    if commander is not None:
        lines.append('  <Cards CatID="0" Quantity="1" Sideboard="true" Name="%s" />' % commander)
    lines.append("</Deck>")
    return "\n".join(lines) + "\n"


def squash(s):
    """Whitespace-insensitive form of an HTML string."""
    return re.sub(r"\s+", "", s)


def stat_entry(name, **kw):
    """A §3.3 card entry with sane defaults for compute_stats tests."""
    e = {
        "name": name, "full_name": name, "qty": 1, "is_commander": False, "mana_cost": "",
        "cmc": 0, "type_line": "Creature", "primary_type": "Creature", "colors": [],
        "color_identity": [], "produced_mana": [], "rarity": "common", "set": "tst",
        "set_name": "Test", "collector_number": "1", "oracle_text": "", "power": None,
        "toughness": None, "loyalty": None, "keywords": [], "artist": "", "layout": "normal",
        "game_changer": False, "price_eur": None,
        "images": {"small": None, "normal": None, "large": None, "png": None, "art_crop": None},
        "scryfall_uri": "https://scryfall.com/x", "faces": None,
    }
    e.update(kw)
    return e


def dek_names_from_file(path):
    """Names (entities decoded) and the Sideboard=true name, read independently of build_site."""
    xml = path.read_text(encoding="utf-8")
    names, cmd = [], None
    for m in re.finditer(r'Sideboard="(true|false)" Name="([^"]*)"', xml):
        n = html.unescape(m.group(2))
        if m.group(1) == "true" and cmd is None:
            cmd = n
        names.append(n)
    return names, cmd


def deck_dir_for(basename):
    """Owner folder that holds <basename>.dek."""
    for d in (IVAN, MIQUEL):
        if (d / (basename + ".dek")).exists():
            return d
    raise AssertionError(f"no .dek for {basename}")


def known_names_for(dek_path):
    dl = build_site.parse_dek(dek_path)
    return [e.name for e in dl.cards if e.name not in build_site.BASIC_LANDS]


# ----------------------------------------------------------------------------- tests

class BuildSiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(CACHE_FILE, encoding="utf-8") as fh:
            cls.cache = json.load(fh)
        cls.dek_paths = build_site.find_deks(DECKS)
        cls.bumble_dek = IVAN / "Ms_Bumbleflower.dek"
        cls.bumble_md = IVAN / "Ms_Bumbleflower.md"
        cls.edgar_dek = IVAN / "Edgar_Markov_-_Vampire_Tribal.dek"
        cls.edgar_md = IVAN / "Edgar_Markov_-_Vampire_Tribal.md"
        cls.sauron_dek = IVAN / "Sauron_the_Dark_Lord_.dek"
        cls.sauron_md = IVAN / "Sauron_the_Dark_Lord_.md"
        cls.hobbits_dek = MIQUEL / "Hobbits.dek"
        cls.hobbits_md = MIQUEL / "Hobbits.md"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write_dek(self, text, name="Synthetic.dek"):
        p = self.tmp / name
        p.write_text(text, encoding="utf-8")
        return p

    def make_temp_root(self, basename):
        """Temp ROOT with decks/<basename>.dek+.md, a cache subset, owners.json and a stale deck json."""
        root = self.tmp / "root"
        (root / "decks" / "_cache").mkdir(parents=True)
        src = deck_dir_for(basename)
        shutil.copy(src / (basename + ".dek"), root / "decks" / (basename + ".dek"))
        shutil.copy(src / (basename + ".md"), root / "decks" / (basename + ".md"))
        names, _ = dek_names_from_file(src / (basename + ".dek"))
        subset = {n: self.cache[n] for n in names}
        (root / "decks" / "_cache" / "cards.json").write_text(
            json.dumps(subset, ensure_ascii=False), encoding="utf-8")
        (root / "decks" / "owners.json").write_text(json.dumps(DEFAULT_OWNERS), encoding="utf-8")
        (root / "docs" / "data" / "decks").mkdir(parents=True)
        (root / "docs" / "data" / "decks" / "stale.json").write_text("{}", encoding="utf-8")
        return root

    # ---- §2.1 slugify

    def test_slugify_basic(self):
        for basename, slug in DEK_SLUGS.items():
            self.assertEqual(build_site.slugify(basename), slug)
        self.assertEqual(build_site.slugify("Nazgûl"), "nazgul")
        self.assertEqual(build_site.slugify("  A -- B "), "a-b")

    # ---- §2.2 parse_dek

    def test_parse_dek_real_totals(self):
        self.assertEqual(len(self.dek_paths), 6)
        for p in self.dek_paths:
            with self.subTest(dek=p.name):
                dl = build_site.parse_dek(p)
                _, cmd = dek_names_from_file(p)
                self.assertEqual(dl.total(), DECK_TOTALS[p.stem])
                self.assertEqual(dl.commander, cmd)
                self.assertEqual(dl.cards[0].name, cmd)
                self.assertEqual(dl.cards[0].qty, 1)
                self.assertTrue(dl.cards[0].sideboard)

    def test_parse_dek_entities(self):
        p = self.write_dek(dek_xml([("Innkeeper&apos;s Talent", 1), ("Fire &amp; Ice", 1)],
                                   commander="Ms. Bumbleflower"))
        dl = build_site.parse_dek(p)
        names = [e.name for e in dl.cards]
        self.assertIn("Innkeeper's Talent", names)
        self.assertIn("Fire & Ice", names)
        self.assertEqual(dl.commander, "Ms. Bumbleflower")
        self.assertEqual(dl.total(), 3)

    def test_parse_dek_basic_qty(self):
        p = self.write_dek(dek_xml([("Forest", 6), ("Sol Ring", 1)], commander="Ms. Bumbleflower"))
        dl = build_site.parse_dek(p)
        self.assertEqual(dl.total(), 8)
        forests = [e for e in dl.cards if e.name == "Forest"]
        self.assertEqual(len(forests), 1)
        self.assertEqual(forests[0].qty, 6)
        self.assertFalse(forests[0].sideboard)

    def test_parse_dek_no_commander_raises(self):
        p = self.write_dek(dek_xml([("Forest", 6), ("Sol Ring", 1)]))
        with self.assertRaises(build_site.BuildError):
            build_site.parse_dek(p)

    # ---- §2.3 primary_type

    def test_primary_type_precedence(self):
        cases = [
            ("Legendary Artifact Creature — Golem", "Creature"),
            ("Enchantment Land — Urza's Saga", "Land"),
            ("Artifact Land", "Land"),
            ("Sorcery // Land", "Sorcery"),
            ("Land // Land", "Land"),
            ("Battle — Siege // Artifact — Equipment", "Battle"),
            ("Kindred Artifact — Goblin", "Artifact"),
            ("Legendary Planeswalker — Tamiyo", "Planeswalker"),
            ("Tribal Instant — Goblin", "Instant"),
            ("Conspiracy", "Other"),
        ]
        for type_line, expected in cases:
            with self.subTest(type_line=type_line):
                self.assertEqual(build_site.primary_type(type_line), expected)

    # ---- §2.4 card_summary

    def test_card_summary_normal(self):
        c = build_site.card_summary(self.cache["Counterspell"])
        keys = set(c.keys())
        self.assertNotIn("qty", keys)
        self.assertNotIn("is_commander", keys)
        self.assertEqual(CARD_KEYS - keys, set(), "missing §3.3 keys")
        self.assertTrue(c["images"]["normal"].startswith("https://cards.scryfall.io/"))
        self.assertEqual(set(c["images"].keys()), {"small", "normal", "large", "png", "art_crop"})
        self.assertIsNone(c["faces"])
        self.assertTrue(c["price_eur"] is None or isinstance(c["price_eur"], float))
        self.assertEqual(c["cmc"], 2)
        self.assertIsInstance(c["cmc"], int)
        self.assertEqual(c["primary_type"], "Instant")
        self.assertEqual(c["colors"], ["U"])
        self.assertEqual(c["set"], "dsc")

    def test_card_summary_mdfc(self):
        c = build_site.card_summary(self.cache["Agadeem's Awakening"])
        self.assertEqual(c["mana_cost"], "{X}{B}{B}{B}")
        self.assertIsNotNone(c["images"]["normal"])
        self.assertTrue(c["images"]["normal"].startswith("https://cards.scryfall.io/"))
        self.assertIsInstance(c["faces"], list)
        self.assertEqual(len(c["faces"]), 2)
        self.assertEqual(c["faces"][1]["type_line"], "Land")
        self.assertEqual(c["faces"][0]["name"], "Agadeem's Awakening")
        self.assertEqual(set(c["faces"][0].keys()),
                         {"name", "mana_cost", "type_line", "oracle_text", "power", "toughness",
                          "loyalty", "colors", "images"})
        self.assertEqual(c["primary_type"], "Sorcery")
        self.assertEqual(c["cmc"], 3)
        self.assertEqual(c["colors"], ["B"])
        # full_name / name are set by build_deck (§2.9)
        deck = build_site.build_deck(self.edgar_dek, None, self.cache, DEFAULT_OWNERS)
        entry = next(e for e in deck["cards"] if e["name"] == "Agadeem's Awakening")
        self.assertEqual(entry["full_name"], "Agadeem's Awakening // Agadeem, the Undercrypt")
        self.assertEqual(entry["produced_mana"], ["B"])

    def test_card_summary_transform_colors(self):
        c = build_site.card_summary(self.cache["Bloodline Keeper"])
        self.assertEqual(c["colors"], ["B"])
        self.assertEqual(c["power"], "3")
        self.assertEqual(c["toughness"], "3")
        self.assertTrue(c["oracle_text"])
        self.assertEqual(c["mana_cost"], "{2}{B}{B}")
        self.assertEqual(c["primary_type"], "Creature")
        self.assertIsInstance(c["faces"], list)
        self.assertEqual(c["faces"][1]["power"], "5")

    def test_card_summary_no_eur(self):
        obj = json.loads(json.dumps(self.cache["Counterspell"]))
        obj["prices"] = {"usd": "1.00", "eur": None}
        self.assertIsNone(build_site.card_summary(obj)["price_eur"])
        obj["prices"] = {}
        self.assertIsNone(build_site.card_summary(obj)["price_eur"])
        del obj["prices"]
        self.assertIsNone(build_site.card_summary(obj)["price_eur"])

    # ---- §2.6 aliases / find_names / wrap_card_refs

    def test_aliases(self):
        names = ["Vito, Thorn of the Dusk Rose", "Edgar Markov", "Edgar, Charmed Groom",
                 "Kid Loki", "Loki, God of Mischief"]
        self.assertEqual(build_site.aliases(names),
                         {"Vito": "Vito, Thorn of the Dusk Rose", "Loki": "Loki, God of Mischief"})

    def test_find_names_longest_first(self):
        names = ["Goblin Chieftain", "Goblin"]
        self.assertEqual(build_site.find_names("Goblin Chieftain y Goblin", names),
                         ["Goblin Chieftain", "Goblin"])
        self.assertEqual(build_site.find_names("Goblin Chieftain", names), ["Goblin Chieftain"])

    def test_find_names_boundaries(self):
        names = ["Anger", "Krenko, Mob Boss", "Vito, Thorn of the Dusk Rose"]
        self.assertEqual(build_site.find_names("Angerbot", names), [])
        self.assertEqual(build_site.find_names("Vito's turn", names), ["Vito, Thorn of the Dusk Rose"])
        self.assertEqual(build_site.find_names("Krenko's goblins", names), ["Krenko, Mob Boss"])
        self.assertEqual(build_site.find_names("d'Anger", names), [])
        # order by first occurrence, deduped
        self.assertEqual(build_site.find_names("Krenko, Mob Boss y Anger y Krenko", names),
                         ["Krenko, Mob Boss", "Anger"])

    def test_wrap_card_refs(self):
        names = ["Whitemane Lion", "Vito, Thorn of the Dusk Rose", "Innkeeper's Talent"]
        out = build_site.wrap_card_refs("Whitemane Lion y Vito.", names)
        self.assertEqual(
            out,
            '<span class="card-ref" data-card="Whitemane Lion">Whitemane Lion</span> y '
            '<span class="card-ref" data-card="Vito, Thorn of the Dusk Rose">Vito</span>.')
        # apostrophe name wraps (text is already html-escaped with quote=False, so ' stays)
        out = build_site.wrap_card_refs("Con Innkeeper's Talent ganas.", names)
        spans = re.findall(r'<span class="card-ref" data-card="([^"]*)">(.*?)</span>', out)
        self.assertEqual(len(spans), 1)
        self.assertEqual(html.unescape(spans[0][0]), "Innkeeper's Talent")
        self.assertEqual(spans[0][1], "Innkeeper's Talent")
        # every occurrence wrapped, never nested
        out = build_site.wrap_card_refs("Vito y Vito, Thorn of the Dusk Rose; Vito otra vez.", names)
        self.assertEqual(out.count('<span class="card-ref"'), 3)
        self.assertEqual(out.count("</span>"), 3)
        for m in re.finditer(r'<span class="card-ref"[^>]*>(.*?)</span>', out):
            self.assertNotIn("<", m.group(1), "nested span inside a card-ref")
        # unknown text untouched
        self.assertEqual(build_site.wrap_card_refs("nada aqui", names), "nada aqui")

    # ---- §2.5 md_to_html

    def test_md_headings_paragraphs_bold_code(self):
        out = build_site.md_to_html("## Idea\n\nTexto **fuerte** con `code` y *cursiva*.")
        self.assertEqual(
            squash(out),
            squash('<h2 id="idea">Idea</h2><p>Texto <strong>fuerte</strong> con <code>code</code> '
                   'y <em>cursiva</em>.</p>'))

    def test_md_escapes_html(self):
        out = build_site.md_to_html("a < b & c")
        self.assertIn("&lt;", out)
        self.assertIn("&amp;", out)
        self.assertNotIn("<p>a < b", out)
        out = build_site.md_to_html("Innkeeper's Talent")
        self.assertIn("Innkeeper's Talent", out)
        self.assertNotIn("&#x27;", out)
        self.assertNotIn("&#39;", out)
        self.assertNotIn("&apos;", out)

    def test_md_lists_nested(self):
        out = build_site.md_to_html("- Pilas habituales:\n  - **A**\n  - B\n- Otro")
        self.assertEqual(
            squash(out),
            squash('<ul><li>Pilas habituales:<ul><li><strong>A</strong></li><li>B</li></ul></li>'
                   '<li>Otro</li></ul>'))

    def test_md_ordered_list(self):
        out = build_site.md_to_html("1. a\n2. b")
        self.assertEqual(squash(out), squash("<ol><li>a</li><li>b</li></ol>"))

    def test_md_blockquote(self):
        out = build_site.md_to_html("> Bracket 4. Lista (`x.dek`).")
        self.assertEqual(
            squash(out),
            squash("<blockquote><p>Bracket 4. Lista (<code>x.dek</code>).</p></blockquote>"))

    def test_md_table(self):
        md = "| Situación | Buscar |\n|---|---|\n| **Tutor** | Rift |\n| Motor | Lion |\n"
        out = build_site.md_to_html(md)
        self.assertIn('<table class="md-table">', out)
        self.assertIn("<thead>", out)
        self.assertEqual(out.count("<th>"), 2)
        tbody = re.search(r"<tbody>(.*?)</tbody>", out, re.S)
        self.assertIsNotNone(tbody)
        self.assertEqual(tbody.group(1).count("<tr>"), 2)
        self.assertEqual(tbody.group(1).count("<td>"), 4)
        self.assertIn("<td><strong>Tutor</strong></td>", squash(tbody.group(1)))
        self.assertIn("<th>Situación</th>", out)

    def test_md_gallery_block(self):
        md = "\n".join([
            "Intro.",
            "",
            build_site.MARK_START,
            "<table>",
            '<tr><td align="center"><img src="img/A.png" alt="Whitemane Lion" title="Whitemane Lion" '
            'width="210"><br><sub>Whitemane Lion</sub></td>'
            '<td align="center"><img src="img/B.png" alt="Innkeeper&#x27;s Talent" title="x" '
            'width="210"><br><sub>Innkeeper&#x27;s Talent</sub></td>'
            '<td align="center"><img src="img/C.png" alt="Narset, Parter of Veils" title="x" '
            'width="210"><br><sub>Narset, Parter of Veils</sub></td></tr>',
            "</table>",
            build_site.MARK_END,
            "",
            "Después.",
        ])
        out = build_site.md_to_html(md)
        self.assertEqual(out.count('<div class="card-gallery"'), 1)
        self.assertNotIn("<img", out)
        self.assertNotIn("<table", out)
        self.assertNotIn("cards:start", out)
        m = re.search(r'<div class="card-gallery" data-cards="([^"]*)"></div>', out)
        self.assertIsNotNone(m, out)
        self.assertEqual(html.unescape(m.group(1)),
                         "Whitemane Lion|Innkeeper's Talent|Narset, Parter of Veils")
        self.assertIn("<p>Intro.</p>", squash(out))
        self.assertIn("<p>Después.</p>", squash(out))
        # a gallery block without images emits nothing
        out = build_site.md_to_html(build_site.MARK_START + "\n<table>\n</table>\n" + build_site.MARK_END)
        self.assertNotIn("card-gallery", out)

    def test_md_raw_html_passthrough(self):
        raw = '<div class="x">hi</div>'
        out = build_site.md_to_html("Antes.\n\n" + raw + "\n\nDespués.")
        self.assertIn(raw, out)
        self.assertNotIn("&lt;div", out)

    def test_md_card_refs_in_heading_and_list(self):
        names = ["Vito, Thorn of the Dusk Rose", "Bloodthirsty Conqueror", "Edgar Markov"]
        out = build_site.md_to_html("### 1. Vito + Bloodthirsty Conqueror\n- Vito drena", names)
        self.assertIn('id="1-vito-bloodthirsty-conqueror"', out)
        spans = re.findall(r'<span class="card-ref" data-card="([^"]*)">([^<]*)</span>', out)
        self.assertEqual([html.unescape(s[0]) for s in spans],
                         ["Vito, Thorn of the Dusk Rose", "Bloodthirsty Conqueror",
                          "Vito, Thorn of the Dusk Rose"])
        self.assertEqual([s[1] for s in spans], ["Vito", "Bloodthirsty Conqueror", "Vito"])
        h = re.search(r"<h3[^>]*>(.*?)</h3>", out, re.S).group(1)
        self.assertEqual(h.count('class="card-ref"'), 2)
        li = re.search(r"<li>(.*?)</li>", out, re.S).group(1)
        self.assertEqual(li.count('class="card-ref"'), 1)
        # not in the H1, not inside <code>
        out = build_site.md_to_html("# Vito\n\n`Vito` y Vito", names)
        self.assertNotIn('<h1 id="vito"><span', out)
        self.assertIn("<code>Vito</code>", out)
        self.assertEqual(out.count('class="card-ref"'), 1)

    # ---- §2.7 parse_md

    def test_parse_md_real_bumbleflower(self):
        known = known_names_for(self.bumble_dek)
        g = build_site.parse_md(self.bumble_md.read_text(encoding="utf-8"), known)
        self.assertEqual(g["title"], "Ms. Bumbleflower")
        self.assertEqual(g["subtitle"], "Bant: G/W/U")
        self.assertEqual(g["bracket"], 4)
        self.assertIn("Bracket 4", g["bracket_text"])
        self.assertIn("`Ms_Bumbleflower.dek`", g["bracket_text"])
        self.assertFalse(g["bracket_text"].startswith(">"))
        ids = [s["id"] for s in g["sections"]]
        for sid in ("idea-general", "cartes-clau", "punts-febles"):
            self.assertIn(sid, ids)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(s["level"] in (2, 3) for s in g["sections"]))
        ck = next(s for s in g["sections"] if s["id"] == "cartes-clau")
        self.assertEqual(ck["level"], 2)
        self.assertEqual(len(ck["gallery"]), 10)
        self.assertEqual(ck["gallery"][0], "Whitemane Lion")
        self.assertIn("Morska, Undersea Sleuth", ck["gallery"])
        self.assertIn("md-table", ck["html"])
        self.assertIn('class="card-gallery"', ck["html"])
        self.assertNotIn("card-gallery", g["intro_html"])
        first3 = next(s for s in g["sections"] if s["level"] == 3)
        self.assertIn("Whitemane Lion", first3["cards"])
        self.assertIn("Shrieking Drake", first3["cards"])
        self.assertIn("Whitemane Lion", g["card_refs"])
        self.assertIn('class="card-ref"', first3["html"])
        self.assertIn('class="card-ref"', first3["heading_html"])
        self.assertEqual(first3["heading"][:3], "1. ")
        self.assertEqual(g["sections"][0]["id"], "idea-general")
        self.assertEqual(g["sections"][0]["heading"], "Idea general")
        self.assertEqual(g["sections"][0]["heading_html"], "Idea general")
        for s in g["sections"]:
            self.assertEqual(set(s.keys()),
                             {"level", "id", "heading", "heading_html", "html", "gallery", "cards"})
        # union of section cards, order of first appearance
        seen = []
        for s in g["sections"]:
            for n in s["cards"]:
                if n not in seen:
                    seen.append(n)
        self.assertEqual(g["card_refs"], seen)

    def test_parse_md_sections_flat_and_ids_unique(self):
        md = "# T (Sub)\n\n> Bracket 3.\n\n## A\n\n### Combo\n\nuno\n\n### Combo\n\ndos\n\n#### Deep\n\ntres\n\n## Combo\n"
        g = build_site.parse_md(md)
        self.assertEqual([s["id"] for s in g["sections"]], ["a", "combo", "combo-2", "combo-3"])
        self.assertEqual([s["level"] for s in g["sections"]], [2, 3, 3, 2])
        self.assertEqual(g["bracket"], 3)
        self.assertEqual(g["title"], "T")
        self.assertEqual(g["subtitle"], "Sub")
        # #### folded into the current section
        self.assertIn("<h4", g["sections"][2]["html"])
        self.assertIn("tres", g["sections"][2]["html"])
        self.assertEqual(g["card_refs"], [])
        self.assertEqual(g["sections"][1]["cards"], [])

    def test_parse_md_without_bracket(self):
        g = build_site.parse_md("# Solo titulo\n\nHola.\n\n## Sec\n\nCuerpo.\n")
        self.assertIsNone(g["bracket"])
        self.assertEqual(g["bracket_text"], "")
        self.assertEqual(g["title"], "Solo titulo")
        self.assertEqual(g["subtitle"], "")
        self.assertIn("<p>Hola.</p>", squash(g["intro_html"]))
        self.assertEqual(len(g["sections"]), 1)

    # ---- §2.8 compute_stats

    def test_compute_stats_synthetic(self):
        cards = [
            stat_entry("Cmd", is_commander=True, mana_cost="{2}{W}{U}", cmc=4, primary_type="Creature",
                       type_line="Legendary Creature", colors=["W", "U"], color_identity=["W", "U"]),
            stat_entry("Hybrid", mana_cost="{W/U}", cmc=1, primary_type="Instant", type_line="Instant",
                       colors=["W", "U"], color_identity=["W", "U"]),
            stat_entry("Phyrexian", mana_cost="{G/P}{G}", cmc=2, primary_type="Creature",
                       type_line="Creature", colors=["G"], color_identity=["G"]),
            stat_entry("Xspell", mana_cost="{X}{R}", cmc=1, primary_type="Sorcery", type_line="Sorcery",
                       colors=["R"], color_identity=["R"]),
            stat_entry("Forest", qty=3, mana_cost="", cmc=0, primary_type="Land",
                       type_line="Basic Land — Forest", colors=[], color_identity=["G"],
                       produced_mana=["G"]),
            stat_entry("Sol Ring", mana_cost="{1}", cmc=1, primary_type="Artifact", type_line="Artifact",
                       colors=[], color_identity=[], produced_mana=["C"], price_eur=2.5),
        ]
        s = build_site.compute_stats(cards, "Cmd")
        self.assertEqual(s["total_cards"], 8)
        self.assertEqual(s["distinct_cards"], 6)
        self.assertEqual(s["land_count"], 3)
        self.assertEqual(s["nonland_count"], 5)
        self.assertEqual(s["by_type"], {"Creature": 2, "Planeswalker": 0, "Battle": 0, "Instant": 1,
                                        "Sorcery": 1, "Artifact": 1, "Enchantment": 0, "Land": 3,
                                        "Other": 0})
        self.assertEqual(s["mana_curve"], {"0": 0, "1": 3, "2": 1, "3": 0, "4": 1, "5": 0, "6": 0,
                                           "7+": 0})
        self.assertEqual(s["avg_mana_value"], 1.8)
        self.assertEqual(s["pips"], {"W": 2, "U": 2, "B": 0, "R": 1, "G": 2, "C": 0, "generic": 3})
        self.assertEqual(s["cards_by_color"], {"W": 0, "U": 0, "B": 0, "R": 1, "G": 1,
                                               "multicolor": 2, "colorless": 1})
        self.assertEqual(s["mana_sources"], {"lands_total": 3, "lands_colored": 3,
                                             "nonland_producers": 1,
                                             "by_color": {"W": 0, "U": 0, "B": 0, "R": 0, "G": 3,
                                                          "C": 1}})
        self.assertEqual(s["price_eur"]["total"], 2.5)
        self.assertEqual(s["price_eur"]["priced_cards"], 1)
        self.assertEqual(s["price_eur"]["unpriced_cards"], 7)
        self.assertEqual(s["price_eur"]["most_expensive"], [{"name": "Sol Ring", "price_eur": 2.5}])
        self.assertEqual(s["color_identity"], ["W", "U", "R", "G"])
        self.assertEqual(s["rarity"], {"common": 8, "uncommon": 0, "rare": 0, "mythic": 0})
        self.assertEqual(s["keywords"], [])
        self.assertEqual(s["game_changers"], [])

    def test_compute_stats_curve_7plus(self):
        cards = [
            stat_entry("A", is_commander=True, cmc=7, mana_cost="{7}", primary_type="Creature"),
            stat_entry("B", cmc=9, mana_cost="{9}", primary_type="Sorcery"),
            stat_entry("C", cmc=12, mana_cost="{12}", primary_type="Artifact"),
            stat_entry("Island", cmc=0, primary_type="Land", qty=2, produced_mana=["U"]),
        ]
        s = build_site.compute_stats(cards, "A")
        self.assertEqual(s["mana_curve"], {"0": 0, "1": 0, "2": 0, "3": 0, "4": 0, "5": 0, "6": 0,
                                           "7+": 3})
        self.assertEqual(sum(s["mana_curve"].values()), s["nonland_count"])
        self.assertEqual(s["avg_mana_value"], round(28 / 3, 2))
        self.assertEqual(s["pips"]["generic"], 28)

    def test_compute_stats_all_keys_present(self):
        deck = build_site.build_deck(self.bumble_dek, self.bumble_md, self.cache, DEFAULT_OWNERS)
        s = deck["stats"]
        self.assertEqual(set(s.keys()), STATS_KEYS)
        self.assertEqual(list(s["by_type"].keys()), build_site.TYPE_ORDER)
        self.assertTrue({"common", "uncommon", "rare", "mythic"} <= set(s["rarity"].keys()))
        self.assertEqual(set(s["mana_curve"].keys()), {"0", "1", "2", "3", "4", "5", "6", "7+"})
        self.assertEqual(set(s["pips"].keys()), {"W", "U", "B", "R", "G", "C", "generic"})
        self.assertEqual(set(s["cards_by_color"].keys()),
                         {"W", "U", "B", "R", "G", "multicolor", "colorless"})
        self.assertEqual(set(s["mana_sources"].keys()),
                         {"lands_total", "lands_colored", "nonland_producers", "by_color"})
        self.assertEqual(set(s["price_eur"].keys()),
                         {"total", "priced_cards", "unpriced_cards", "most_expensive"})
        self.assertEqual(sum(s["by_type"].values()), 100)
        self.assertEqual(sum(s["mana_curve"].values()), s["nonland_count"])
        self.assertEqual(s["land_count"] + s["nonland_count"], 100)
        self.assertEqual(s["color_identity"], ["W", "U", "G"])
        self.assertLessEqual(len(s["price_eur"]["most_expensive"]), 5)
        self.assertLessEqual(len(s["keywords"]), 10)
        self.assertIn("Cyclonic Rift", s["game_changers"])
        self.assertEqual(s["game_changers"], sorted(s["game_changers"]))
        self.assertEqual(s["price_eur"]["priced_cards"] + s["price_eur"]["unpriced_cards"], 100)

    # ---- §2.9 build_deck

    def test_build_deck_real_all(self):
        for p in self.dek_paths:
            basename = p.stem
            with self.subTest(dek=p.name):
                md = p.with_suffix(".md")
                self.assertTrue(md.exists())
                deck = build_site.build_deck(p, md, self.cache, DEFAULT_OWNERS)
                total = DECK_TOTALS[basename]
                self.assertEqual(sum(c["qty"] for c in deck["cards"]), total)
                self.assertTrue(deck["cards"][0]["is_commander"])
                self.assertEqual(sum(1 for c in deck["cards"] if c["is_commander"]),
                                 len(deck["commanders"]))
                for c in deck["cards"]:
                    self.assertTrue(c["images"]["normal"], c["name"])
                    self.assertTrue(c["scryfall_uri"], c["name"])
                    self.assertIn(c["primary_type"], build_site.TYPE_ORDER)
                    self.assertEqual(set(c.keys()), CARD_KEYS | {"qty", "is_commander", "roles"})
                self.assertEqual(deck["stats"]["total_cards"], total)
                self.assertIsNotNone(deck["guide"])
                self.assertEqual(deck["slug"], DEK_SLUGS[basename])
                self.assertEqual(deck["owner"], "Ivan")
                self.assertEqual(deck["dek_file"], p.name)
                self.assertEqual(deck["md_file"], md.name)
                self.assertEqual(deck["bracket"], 3 if basename == "Hobbits" else 4)
                self.assertEqual(deck["commander"], deck["cards"][0])
                self.assertEqual(deck["title"], deck["guide"]["title"])
                self.assertTrue(deck["guide"]["sections"])
                self.assertEqual(
                    set(deck.keys()),
                    {"slug", "dek_file", "md_file", "title", "subtitle", "owner", "bracket",
                     "bracket_text", "commander", "commanders", "cards", "stats", "guide"})
                # every card referenced by the guide exists in the deck
                names = {c["name"] for c in deck["cards"]}
                for s in deck["guide"]["sections"]:
                    for n in s["gallery"] + s["cards"]:
                        self.assertIn(n, names)
                    for m in re.finditer(r'data-card="([^"]*)"', s["html"] + s["heading_html"]):
                        self.assertIn(html.unescape(m.group(1)), names)

    def test_build_deck_missing_card_raises(self):
        p = self.write_dek(dek_xml([("Forest", 3), ("Carta Inexistente XYZ", 1)],
                                   commander="Ms. Bumbleflower"))
        with self.assertRaises(build_site.MissingCardError) as ctx:
            build_site.build_deck(p, None, self.cache, DEFAULT_OWNERS)
        self.assertIn("Carta Inexistente XYZ", str(ctx.exception))
        self.assertIn(p.name, str(ctx.exception))
        self.assertTrue(issubclass(build_site.MissingCardError, build_site.BuildError))

    def test_build_deck_no_md(self):
        deck = build_site.build_deck(self.bumble_dek, None, self.cache, DEFAULT_OWNERS)
        self.assertIsNone(deck["guide"])
        self.assertIsNone(deck["md_file"])
        self.assertEqual(deck["title"], "Ms Bumbleflower")
        self.assertEqual(deck["subtitle"], "")
        self.assertIsNone(deck["bracket"])
        self.assertEqual(deck["bracket_text"], "")
        self.assertEqual(deck["slug"], "ms-bumbleflower")
        self.assertEqual(deck["stats"]["total_cards"], 100)
        # commander first, then .dek document order
        names, _ = dek_names_from_file(self.bumble_dek)
        expected = ["Ms. Bumbleflower"] + [n for n in names if n != "Ms. Bumbleflower"]
        self.assertEqual([c["name"] for c in deck["cards"]], expected)
        # DFC name handling on a deck with one
        edgar = build_site.build_deck(self.edgar_dek, None, self.cache, DEFAULT_OWNERS)
        self.assertEqual(edgar["title"], "Edgar Markov - Vampire Tribal")
        bk = next(c for c in edgar["cards"] if c["name"] == "Bloodline Keeper")
        self.assertEqual(bk["full_name"], "Bloodline Keeper // Lord of Lineage")

    def test_build_deck_owner_override(self):
        owners = {"default": "Ivan", "decks": {"Ms_Bumbleflower": "Anna"}}
        deck = build_site.build_deck(self.bumble_dek, self.bumble_md, self.cache, owners)
        self.assertEqual(deck["owner"], "Anna")
        other = build_site.build_deck(self.edgar_dek, None, self.cache, owners)
        self.assertEqual(other["owner"], "Ivan")

    def test_find_deks_includes_owner_folders(self):
        found = build_site.find_deks(DECKS)
        names = {p.name for p in found}
        self.assertIn("Hobbits.dek", names)
        self.assertIn("Ms_Bumbleflower.dek", names)
        # reserved folders are never scanned
        self.assertFalse(any(p.parent.name in build_site.RESERVED_DIRS for p in found))

    def test_find_deks_skips_reserved_and_hidden_dirs(self):
        decks = self.tmp / "decks"
        (decks / "Ivan").mkdir(parents=True)
        (decks / "_cache").mkdir()
        (decks / ".hidden").mkdir()
        (decks / "Ivan" / "A.dek").write_text("<Deck/>", encoding="utf-8")
        (decks / "_cache" / "B.dek").write_text("<Deck/>", encoding="utf-8")
        (decks / ".hidden" / "C.dek").write_text("<Deck/>", encoding="utf-8")
        (decks / "D.dek").write_text("<Deck/>", encoding="utf-8")
        self.assertEqual([p.name for p in build_site.find_deks(decks)], ["D.dek", "A.dek"])

    def test_deck_owner_from_folder(self):
        owners = {"default": "Ivan", "decks": {}}
        decks = self.tmp / "decks"
        (decks / "Miquel").mkdir(parents=True)
        self.assertEqual(build_site.deck_owner(decks / "Miquel" / "X.dek", owners, decks), "Miquel")
        # loose .dek -> default; no decks_dir -> default (the folder rule is opt-in)
        self.assertEqual(build_site.deck_owner(decks / "X.dek", owners, decks), "Ivan")
        self.assertEqual(build_site.deck_owner(decks / "Miquel" / "X.dek", owners), "Ivan")
        # owners.json wins over the folder
        named = {"default": "Ivan", "decks": {"X": "Anna"}}
        self.assertEqual(build_site.deck_owner(decks / "Miquel" / "X.dek", named, decks), "Anna")

    def test_build_deck_owner_from_folder(self):
        deck = build_site.build_deck(self.hobbits_dek, self.hobbits_md, self.cache,
                                     DEFAULT_OWNERS, decks_dir=DECKS)
        self.assertEqual(deck["owner"], "Miquel")

    def test_partner_commanders(self):
        dl = build_site.parse_dek(self.hobbits_dek)
        self.assertEqual(dl.commanders,
                         ["Frodo, Adventurous Hobbit", "Sam, Loyal Attendant"])
        self.assertEqual(dl.commander, "Frodo, Adventurous Hobbit")
        self.assertTrue(all(e.sideboard for e in dl.cards[:2]))
        self.assertFalse(any(e.sideboard for e in dl.cards[2:]))
        deck = build_site.build_deck(self.hobbits_dek, None, self.cache, DEFAULT_OWNERS,
                                     roles_path=DECKS / "roles" / "Hobbits.json")
        self.assertEqual(deck["commanders"], dl.commanders)
        self.assertEqual([c["name"] for c in deck["cards"] if c["is_commander"]], dl.commanders)

    # ---- §2.10 build_index / build_all

    def test_build_index(self):
        owners = {"default": "Ivan", "decks": {"Edgar_Markov_-_Vampire_Tribal": "Anna"}}
        bumble = build_site.build_deck(self.bumble_dek, self.bumble_md, self.cache, owners)
        edgar = build_site.build_deck(self.edgar_dek, self.edgar_md, self.cache, owners)
        sauron = build_site.build_deck(self.sauron_dek, None, self.cache, owners)
        index = build_site.build_index([sauron, bumble, edgar])
        self.assertEqual(set(index.keys()), {"generated_at", "owners", "decks", "roles"})
        self.assertEqual(index["owners"], ["Anna", "Ivan"])
        self.assertRegex(index["generated_at"], r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        titles = [d["title"] for d in index["decks"]]
        self.assertEqual(titles, sorted(titles, key=str.lower))
        self.assertEqual(titles[0], edgar["title"])
        self.assertEqual(titles[-1], sauron["title"])
        for d, src in zip(index["decks"], [edgar, bumble, sauron]):
            self.assertEqual(set(d.keys()), INDEX_DECK_KEYS)
            self.assertEqual(d["slug"], src["slug"])
            self.assertEqual(d["title"], src["title"])
            self.assertEqual(d["subtitle"], src["subtitle"])
            self.assertEqual(d["owner"], src["owner"])
            self.assertEqual(d["bracket"], src["bracket"])
            self.assertEqual(d["card_count"], 100)
            self.assertEqual(d["color_identity"], src["stats"]["color_identity"])
            self.assertEqual(set(d["commander"].keys()), {"name", "art_crop", "normal"})
            self.assertEqual(d["commander"]["name"], src["commander"]["name"])
            self.assertTrue(d["commander"]["art_crop"])
            self.assertTrue(d["commander"]["art_crop"].startswith("https://cards.scryfall.io/"))
            self.assertTrue(d["commander"]["normal"])
            self.assertEqual(d["has_guide"], src["guide"] is not None)
            self.assertEqual(d["price_eur"], src["stats"]["price_eur"]["total"])
            self.assertEqual(d["file"], "data/decks/%s.json" % src["slug"])
        self.assertFalse(index["decks"][2]["has_guide"])
        self.assertEqual(index["decks"][0]["owner"], "Anna")
        self.assertEqual(index["decks"][1]["color_identity"], ["W", "U", "G"])

    def test_build_all_writes_files(self):
        root = self.make_temp_root("Ms_Bumbleflower")
        stale = root / "docs" / "data" / "decks" / "stale.json"
        self.assertTrue(stale.exists())
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = build_site.build_all(root)
        self.assertIn("OK ms-bumbleflower 100 cards", buf.getvalue())
        index_file = root / "docs" / "data" / "index.json"
        deck_file = root / "docs" / "data" / "decks" / "ms-bumbleflower.json"
        self.assertTrue(index_file.exists())
        self.assertTrue(deck_file.exists())
        self.assertTrue((root / "docs" / ".nojekyll").exists())
        self.assertFalse(stale.exists())
        index = json.loads(index_file.read_text(encoding="utf-8"))
        deck = json.loads(deck_file.read_text(encoding="utf-8"))
        self.assertEqual(result, index)
        self.assertEqual(len(index["decks"]), 1)
        self.assertEqual(index["decks"][0]["slug"], "ms-bumbleflower")
        self.assertEqual(index["decks"][0]["file"], "data/decks/ms-bumbleflower.json")
        self.assertEqual(index["owners"], ["Ivan"])
        self.assertEqual(deck["slug"], "ms-bumbleflower")
        self.assertEqual(sum(c["qty"] for c in deck["cards"]), 100)
        self.assertIsNotNone(deck["guide"])
        self.assertTrue(index_file.read_text(encoding="utf-8").endswith("\n"))
        self.assertTrue(deck_file.read_text(encoding="utf-8").endswith("\n"))
        # sort_keys=True
        self.assertEqual(list(deck.keys()), sorted(deck.keys()))
        # nothing copied from decks/img or _cache
        for f in (root / "docs").rglob("*"):
            self.assertNotIn("_cache", f.name)
        text = deck_file.read_text(encoding="utf-8")
        self.assertNotIn("img/", text.replace("cards.scryfall.io", ""))

    def test_json_is_utf8_no_ascii_escapes(self):
        root = self.make_temp_root("Sauron_the_Dark_Lord_")
        with contextlib.redirect_stdout(io.StringIO()):
            build_site.build_all(root)
        deck_file = root / "docs" / "data" / "decks" / "sauron-the-dark-lord.json"
        self.assertTrue(deck_file.exists())
        raw = deck_file.read_bytes()
        text = raw.decode("utf-8")
        self.assertIn("Nazgûl", text)
        self.assertNotIn("Nazg\\u00fbl", text)
        self.assertNotIn("\\u00fb", text)
        deck = json.loads(text)
        naz = [c for c in deck["cards"] if c["name"] == "Nazgûl"]
        self.assertEqual(len(naz), 1, "duplicate .dek entries must be merged")
        self.assertEqual(naz[0]["qty"], 9)
        self.assertEqual(deck["title"], "Sauron, the Dark Lord")
        index_text = (root / "docs" / "data" / "index.json").read_text(encoding="utf-8")
        self.assertNotIn("\\u", index_text)


if __name__ == "__main__":
    unittest.main()


# ----------------------------------------------------------------------------- events (§11)

EVENTS = ROOT / "events"


def set_card(name, **kw):
    """A minimal Scryfall object for a synthetic set cache."""
    c = {
        "name": name, "set": "tst", "collector_number": "1", "rarity": "common",
        "type_line": "Creature — Test", "mana_cost": "{1}", "cmc": 1, "colors": ["W"],
        "color_identity": ["W"], "oracle_text": "", "keywords": [], "layout": "normal",
        "scryfall_uri": "https://scryfall.com/x", "artist": "a", "prices": {"eur": "0.10"},
        "image_uris": {k: f"https://cards.scryfall.io/{k}/{name.replace(' ', '_')}.jpg"
                       for k in build_site.IMAGE_KEYS},
    }
    c.update(kw)
    return c


class EventTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "root"
        decks = self.root / "decks"
        (decks / "_cache" / "sets").mkdir(parents=True)
        (decks / "_cache" / "cards.json").write_text(json.dumps({
            "Old Card": set_card("Old Card", set="old"),
        }), encoding="utf-8")
        cards = [
            set_card("Plain Hero"),
            set_card("Bold Hero // Quick Trick", layout="adventure", oracle_text=None,
                     card_faces=[{"name": "Bold Hero", "type_line": "Creature — Human", "mana_cost": "{1}{W}",
                                  "oracle_text": "Vigilance"},
                                 {"name": "Quick Trick", "type_line": "Instant — Adventure",
                                  "mana_cost": "{W}", "oracle_text": "Scry 2."}]),
            set_card("Azog, Test Ruin", rarity="rare"),
            set_card("Plains", type_line="Basic Land — Plains"),
        ]
        (decks / "_cache" / "sets" / "tst.json").write_text(
            json.dumps({"set": "tst", "name": "Test Set", "cards": cards}), encoding="utf-8")
        self.event = self.root / "events" / "Test_Event"
        self.event.mkdir(parents=True)
        (self.event / "event.json").write_text(json.dumps({
            "title": "Test Event", "date": "2026-09-26", "time": None,
            "location": {"name": "Somewhere", "url": "https://maps.example/x"},
            "set": "tst", "art_card": "Azog, Test Ruin", "languages": ["ca", "it"],
            "default_lang": "ca", "extra_cards": ["Old Card"],
        }), encoding="utf-8")
        (self.event / "event.ca.md").write_text(
            "# Títol (Subtítol)\n\nIntro amb Plain Hero i Old Card.\n\n"
            "<!-- cards:start -->\n<img alt=\"Bold Hero\"><img alt=\"Plains\">\n<!-- cards:end -->\n\n"
            "## Secció\n\nAzog fa coses. Bold Hero també.\n", encoding="utf-8")
        (self.event / "event.it.md").write_text("# Titolo\n\n## Sezione\n\nPlain Hero.\n", encoding="utf-8")
        (self.event / "set.ca.md").write_text("# Guia\n\n## Bombes\n\nAzog, Test Ruin.\n", encoding="utf-8")
        self.cache = json.loads((decks / "_cache" / "cards.json").read_text(encoding="utf-8"))

    def tearDown(self):
        self._tmp.cleanup()

    def test_load_set_cache_uses_front_face_names(self):
        name, cards = build_site.load_set_cache("tst", self.root / "decks")
        self.assertEqual(name, "Test Set")
        self.assertIn("Bold Hero", cards)
        self.assertNotIn("Bold Hero // Quick Trick", cards)
        self.assertEqual(cards["Plain Hero"]["set_name"], "Test Set")
        with self.assertRaises(build_site.BuildError):
            build_site.load_set_cache("nope", self.root / "decks")

    def test_build_event_pages_cards_and_art(self):
        ev = build_site.build_event(self.event, self.cache, decks_dir=self.root / "decks")
        self.assertEqual(ev["slug"], "test-event")
        self.assertEqual(ev["languages"], ["ca", "it"])
        self.assertEqual(ev["default_lang"], "ca")
        self.assertEqual(ev["set"], {"code": "tst", "name": "Test Set"})
        self.assertEqual(ev["location"]["name"], "Somewhere")
        self.assertTrue(ev["art"].endswith("art_crop/Azog,_Test_Ruin.jpg"))
        ca = ev["pages"]["ca"]
        self.assertEqual(ca["event"]["title"], "Títol")
        self.assertEqual(ca["event"]["subtitle"], "Subtítol")
        self.assertNotIn("bracket", ca["event"])
        self.assertEqual([s["heading"] for s in ca["event"]["sections"]], ["Secció"])
        self.assertEqual(ca["event"]["sections"][0]["gallery"], [])
        self.assertIsNotNone(ca["set"])
        self.assertIsNone(ev["pages"]["it"]["set"])
        # cited in the intro, by alias, in a gallery, or from extra_cards: all exported
        for n in ("Plain Hero", "Old Card", "Bold Hero", "Azog, Test Ruin"):
            self.assertIn(n, ev["cards"], n)
        self.assertNotIn("Plains", ev["cards"])
        self.assertEqual(ev["cards"]["Bold Hero"]["name"], "Bold Hero")
        self.assertEqual(ev["cards"]["Bold Hero"]["full_name"], "Bold Hero // Quick Trick")
        self.assertEqual(ev["cards"]["Old Card"]["set"], "old")
        self.assertIn('data-card="Azog, Test Ruin"', ca["event"]["sections"][0]["html"])
        self.assertIn('data-card="Plain Hero"', ca["event"]["intro_html"])

    def test_build_event_errors(self):
        (self.event / "event.it.md").unlink()
        with self.assertRaises(build_site.BuildError):
            build_site.build_event(self.event, self.cache, decks_dir=self.root / "decks")
        (self.event / "event.it.md").write_text("# X\n", encoding="utf-8")
        meta = json.loads((self.event / "event.json").read_text(encoding="utf-8"))
        meta["extra_cards"] = ["Missing Card"]
        (self.event / "event.json").write_text(json.dumps(meta), encoding="utf-8")
        with self.assertRaises(build_site.MissingCardError):
            build_site.build_event(self.event, self.cache, decks_dir=self.root / "decks")
        meta["extra_cards"] = []
        meta["languages"] = []
        (self.event / "event.json").write_text(json.dumps(meta), encoding="utf-8")
        with self.assertRaises(build_site.BuildError):
            build_site.build_event(self.event, self.cache, decks_dir=self.root / "decks")

    def test_build_events_writes_index_and_prunes(self):
        out = self.root / "docs" / "data" / "events"
        out.mkdir(parents=True)
        (out / "stale.json").write_text("{}", encoding="utf-8")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            index = build_site.build_events(self.root, self.cache)
        self.assertIn("OK event test-event (ca, it", buf.getvalue())
        self.assertFalse((out / "stale.json").exists())
        self.assertTrue((out / "test-event.json").exists())
        written = json.loads((out / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(written, index)
        self.assertEqual(len(index["events"]), 1)
        e = index["events"][0]
        self.assertEqual(e["file"], "data/events/test-event.json")
        self.assertEqual(e["languages"], ["ca", "it"])
        self.assertNotIn("pages", e)
        self.assertNotIn("cards", e)

    def test_build_events_without_events_dir(self):
        shutil.rmtree(self.root / "events")
        with contextlib.redirect_stdout(io.StringIO()):
            index = build_site.build_events(self.root, self.cache)
        self.assertEqual(index["events"], [])
        self.assertTrue((self.root / "docs" / "data" / "events" / "index.json").exists())

    def test_real_events_build_with_every_card_resolved(self):
        with open(CACHE_FILE, encoding="utf-8") as fh:
            cache = json.load(fh)
        folders = build_site.find_events(EVENTS)
        self.assertTrue(folders)
        for folder in folders:
            ev = build_site.build_event(folder, cache, decks_dir=DECKS)
            self.assertTrue(ev["cards"], folder.name)
            for lang, pages in ev["pages"].items():
                self.assertIsNotNone(pages["event"], f"{folder.name}: {lang}")
                for page in pages.values():
                    if page is None:
                        continue
                    for s in page["sections"]:
                        for n in s["gallery"]:
                            self.assertIn(n, ev["cards"], f"{folder.name} {lang}: gallery {n}")
                    for n in re.findall(r'data-card="([^"]+)"', page["intro_html"]
                                        + "".join(s["html"] + s["heading_html"] for s in page["sections"])):
                        self.assertIn(html.unescape(n), ev["cards"], f"{folder.name} {lang}: ref {n}")
            for card in ev["cards"].values():
                self.assertTrue(card["images"]["normal"], card["name"])
