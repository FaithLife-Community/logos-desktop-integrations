#!/usr/bin/python3
"""Logos Plasma integrations backend: KRunner D-Bus runner + helpers for the Plasma widgets.

Part of https://github.com/FaithLife-Community/logos-desktop-integrations (GPL-3.0-or-later).
A Raycast/BibleWorks-style command line for Logos on Linux:

  o John 3:16          pick a Bible (your top Bibles are listed; Enter = first)
  oesv John 3:16       open a specific Bible (o + any owned Bible's abbreviation)
  s grace faith        pick a Bible to search in;  sesv grace  searches the ESV
  'Jesus wept          exact phrase (pick a Bible)    .God love   words, any order
  ol bdag              open any book in your library by title/abbreviation
  otc Ruth 1:1         Text Comparison of your top Bibles
  logos [filter]       list every command

Bibles, covers and priorities come straight from Logos's own catalog and
prioritization databases (read-only). Links are handed to Ou Dedetai's URL
handler; afterwards KWin is asked to raise the Logos window.

  rp [filter]          today's readings from your reading plans

Settings and extra commands: ~/.config/logos-plasma/commands.toml
CLI: --check | --focus-test | --reading-plans (JSON) | --open URL
"""
import datetime
import glob
import json
import os
import re
import shutil
import sqlite3
import sys
import time
import tomllib
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

BUS_NAME = "io.github.FaithlifeCommunity.LogosPlasma"
OBJ_PATH = "/runner"
IFACE = "org.kde.krunner1"
INTERNAL_IFACE = "io.github.FaithlifeCommunity.LogosPlasma.Internal"
SEARCH_PATH = "/searchprovider"  # GNOME Shell search provider
SEARCH_IFACE = "org.gnome.Shell.SearchProvider2"

HOME = Path.home()
XDG_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))
XDG_DATA = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share"))
CONFIG_PATH = XDG_CONFIG / "logos-plasma" / "commands.toml"

HIGHEST, MODERATE, LOW = 100, 50, 30  # KRunner CategoryRelevance values

DEFAULTS = {
    "aliases": {
        "open": "o", "search": "s", "phrase": "'", "words": ".",
        "library": "ol", "compare": "otc", "help": "logos",
        "lexicon": "lex", "top": "stb", "everything": "sll", "plans": "rp",
        "wordstudy": "ws", "factbook": "fb", "recent": "or", "devotional": "today",
        "layout": "lay", "copy": "cv",
    },
    "settings": {
        "logos_data": "",            # path to .../AppData/Local/Logos; empty = find Ou Dedetai's
        "bible_aliases": True,       # generate o<abbr> / s<abbr> for every owned Bible
        "picker_bibles": [],         # e.g. ["ESV", "LSB", "NASB95"]; empty = automatic
        "picker_order": "usage",     # "usage" = most opened first, "priority" = Logos's Prioritize list
        "picker_size": 6,
        "covers": True,
        "focus": True,
        "window_classes": ["logos.exe", "verbum.exe"],
        "handler": "",               # .desktop id; empty = whatever handles logos4:
        "safe_chars": ":,.",
        "open_url": "logosres:{logosres};ref=Bible.{q}",
        "search_url": "logos4:Search;kind=MorphSearch;q={q};syntax=v2;documentlevel=verse;"
                      "match=stem;in=raw:{scope};viewkind=passages",
        "phrase_url": "logos4:Search;kind=MorphSearch;q=%22{q}%22;syntax=v2;documentlevel=verse;"
                      "match=stem;in=raw:{scope};viewkind=passages",
        "compare_url": "logos4:TextComparison;ref=Bible.{q};res={resources}",
        "headword_url": "logosres:{logosres};hw={q}",
        # Scopes copied from Logos's own search history (Top Bibles / Your Books).
        "top_bibles_scope": "Top|DataType=bible|ResourceType=text.monograph.bible|ResultLimit=5|Title=Top%2520Bibles",
        "library_search_url": "logos4:Search;kind=BooksSearch;q={q};in=raw:AllVisible|Title=Your%2520Books",
        "search_top_row": True,      # offer "Top Bibles" as the first row of search pickers
        "wordstudy_url": "logos4:Guide;t=Bible%20Word%20Study;hw={q}",
        "factbook_url": "logos4:Factbook;id=ref%3A{key};lens=all",
        # Opened by the "look up" shortcut and bare references in KRunner. logosref: uses the
        # preferred Bible set in Logos; use e.g. "logosres:esv;ref=Bible.{q}" for a fixed one.
        "reference_url": "logosref:Bible.{q}",
        "bare_references": True,     # typing just "John 3:16" in KRunner offers Logos
        "devotionals": [],           # titles/abbreviations; empty = your prioritized devotionals
        "devotional_url": "logosres:{logosres}",  # Logos opens calendar devotionals at today
        "reminders": True,           # reading-plan notifications at each plan's reminder time
        # Books that aren't downloaded yet open by link and Logos offers the download.
        # Set to false to get a notification (title on the clipboard) instead of the link,
        # if opening such books from outside Logos ever misbehaves.
        "link_cloud_books": True,
        "showcase_sermon_commentaries": 60,  # at most this many of your 4–5★ commentaries on the passage
        "devotional_reminder": "",   # e.g. "07:30" for a daily devotional notification
    },
}


def log(*args):
    print("logos-plasma:", *args, file=sys.stderr, flush=True)


def norm(s):
    """Abbreviation → alias key: 'KJV 1900' → 'kjv1900', 'NASB95' → 'nasb95'."""
    return re.sub(r"[\s.\-_/()]+", "", s).lower()


def encode(text, safe):
    return urllib.parse.quote(text, safe=safe)


# ── Logos data ───────────────────────────────────────────────────────────────

BOOKS = {1: "Genesis", 2: "Exodus", 3: "Leviticus", 4: "Numbers", 5: "Deuteronomy", 6: "Joshua",
         7: "Judges", 8: "Ruth", 9: "1 Samuel", 10: "2 Samuel", 11: "1 Kings", 12: "2 Kings",
         13: "1 Chronicles", 14: "2 Chronicles", 15: "Ezra", 16: "Nehemiah", 17: "Esther",
         18: "Job", 19: "Psalm", 20: "Proverbs", 21: "Ecclesiastes", 22: "Song of Songs",
         23: "Isaiah", 24: "Jeremiah", 25: "Lamentations", 26: "Ezekiel", 27: "Daniel",
         28: "Hosea", 29: "Joel", 30: "Amos", 31: "Obadiah", 32: "Jonah", 33: "Micah",
         34: "Nahum", 35: "Habakkuk", 36: "Zephaniah", 37: "Haggai", 38: "Zechariah",
         39: "Malachi", 61: "Matthew", 62: "Mark", 63: "Luke", 64: "John", 65: "Acts",
         66: "Romans", 67: "1 Corinthians", 68: "2 Corinthians", 69: "Galatians",
         70: "Ephesians", 71: "Philippians", 72: "Colossians", 73: "1 Thessalonians",
         74: "2 Thessalonians", 75: "1 Timothy", 76: "2 Timothy", 77: "Titus", 78: "Philemon",
         79: "Hebrews", 80: "James", 81: "1 Peter", 82: "2 Peter", 83: "1 John", 84: "2 John",
         85: "3 John", 86: "Jude", 87: "Revelation"}


BOOK_ABBR = {1: "Gen", 2: "Exod", 3: "Lev", 4: "Num", 5: "Deut", 6: "Josh", 7: "Judg", 8: "Ruth",
             9: "1 Sam", 10: "2 Sam", 11: "1 Kgs", 12: "2 Kgs", 13: "1 Chr", 14: "2 Chr", 15: "Ezra",
             16: "Neh", 17: "Esth", 18: "Job", 19: "Ps", 20: "Prov", 21: "Eccl", 22: "Song",
             23: "Isa", 24: "Jer", 25: "Lam", 26: "Ezek", 27: "Dan", 28: "Hos", 29: "Joel",
             30: "Amos", 31: "Obad", 32: "Jonah", 33: "Mic", 34: "Nah", 35: "Hab", 36: "Zeph",
             37: "Hag", 38: "Zech", 39: "Mal", 61: "Matt", 62: "Mark", 63: "Luke", 64: "John",
             65: "Acts", 66: "Rom", 67: "1 Cor", 68: "2 Cor", 69: "Gal", 70: "Eph", 71: "Phil",
             72: "Col", 73: "1 Thess", 74: "2 Thess", 75: "1 Tim", 76: "2 Tim", 77: "Titus",
             78: "Phlm", 79: "Heb", 80: "Jas", 81: "1 Pet", 82: "2 Pet", 83: "1 John", 84: "2 John",
             85: "3 John", 86: "Jude", 87: "Rev"}

# Verses per chapter, Genesis–Malachi then Matthew–Revelation (English versification).
_VERSES = "31,25,24,26,32,22,24,22,29,32,32,20,18,24,21,16,27,33,38,18,34,24,20,67,34,35,46,22,35,43,55,32,20,31,29,43,36,30,23,23,57,38,34,34,28,34,31,22,33,26;22,25,22,31,23,30,25,32,35,29,10,51,22,31,27,36,16,27,25,26,36,31,33,18,40,37,21,43,46,38,18,35,23,35,35,38,29,31,43,38;17,16,17,35,19,30,38,36,24,20,47,8,59,57,33,34,16,30,37,27,24,33,44,23,55,46,34;54,34,51,49,31,27,89,26,23,36,35,16,33,45,41,50,13,32,22,29,35,41,30,25,18,65,23,31,40,16,54,42,56,29,34,13;46,37,29,49,33,25,26,20,29,22,32,32,18,29,23,22,20,22,21,20,23,30,25,22,19,19,26,68,29,20,30,52,29,12;18,24,17,24,15,27,26,35,27,43,23,24,33,15,63,10,18,28,51,9,45,34,16,33;36,23,31,24,31,40,25,35,57,18,40,15,25,20,20,31,13,31,30,48,25;22,23,18,22;28,36,21,22,12,21,17,22,27,27,15,25,23,52,35,23,58,30,24,42,15,23,29,22,44,25,12,25,11,31,13;27,32,39,12,25,23,29,18,13,19,27,31,39,33,37,23,29,33,43,26,22,51,39,25;53,46,28,34,18,38,51,66,28,29,43,33,34,31,34,34,24,46,21,43,29,53;18,25,27,44,27,33,20,29,37,36,21,21,25,29,38,20,41,37,37,21,26,20,37,20,30;54,55,24,43,26,81,40,40,44,14,47,40,14,17,29,43,27,17,19,8,30,19,32,31,31,32,34,21,30;17,18,17,22,14,42,22,18,31,19,23,16,22,15,19,14,19,34,11,37,20,12,21,27,28,23,9,27,36,27,21,33,25,33,27,23;11,70,13,24,17,22,28,36,15,44;11,20,32,23,19,19,73,18,38,39,36,47,31;22,23,15,17,14,14,10,17,32,3;22,13,26,21,27,30,21,22,35,22,20,25,28,22,35,22,16,21,29,29,34,30,17,25,6,14,23,28,25,31,40,22,33,37,16,33,24,41,30,24,34,17;6,12,8,8,12,10,17,9,20,18,7,8,6,7,5,11,15,50,14,9,13,31,6,10,22,12,14,9,11,12,24,11,22,22,28,12,40,22,13,17,13,11,5,26,17,11,9,14,20,23,19,9,6,7,23,13,11,11,17,12,8,12,11,10,13,20,7,35,36,5,24,20,28,23,10,12,20,72,13,19,16,8,18,12,13,17,7,18,52,17,16,15,5,23,11,13,12,9,9,5,8,28,22,35,45,48,43,13,31,7,10,10,9,8,18,19,2,29,176,7,8,9,4,8,5,6,5,6,8,8,3,18,3,3,21,26,9,8,24,13,10,7,12,15,21,10,20,14,9,6;33,22,35,27,23,35,27,36,18,32,31,28,25,35,33,33,28,24,29,30,31,29,35,34,28,28,27,28,27,33,31;18,26,22,16,20,12,29,17,18,20,10,14;17,17,11,16,16,13,13,14;31,22,26,6,30,13,25,22,21,34,16,6,22,32,9,14,14,7,25,6,17,25,18,23,12,21,13,29,24,33,9,20,24,17,10,22,38,22,8,31,29,25,28,28,25,13,15,22,26,11,23,15,12,17,13,12,21,14,21,22,11,12,19,12,25,24;19,37,25,31,31,30,34,22,26,25,23,17,27,22,21,21,27,23,15,18,14,30,40,10,38,24,22,17,32,24,40,44,26,22,19,32,21,28,18,16,18,22,13,30,5,28,7,47,39,46,64,34;22,22,66,22,22;28,10,27,17,17,14,27,18,11,22,25,28,23,23,8,63,24,32,14,49,32,31,49,27,17,21,36,26,21,26,18,32,33,31,15,38,28,23,29,49,26,20,27,31,25,24,23,35;21,49,30,37,31,28,28,27,27,21,45,13;11,23,5,19,15,11,16,14,17,15,12,14,16,9;20,32,21;15,16,15,13,27,14,17,14,15;21;17,10,10,11;16,13,12,13,15,16,20;15,13,19;17,20,19;18,15,20;15,23;21,13,10,14,11,15,14,23,17,12,17,14,9,21;14,17,18,6;25,23,17,25,48,34,29,34,38,42,30,50,58,36,39,28,27,35,30,34,46,46,39,51,46,75,66,20;45,28,35,41,43,56,37,38,50,52,33,44,37,72,47,20;80,52,38,44,39,49,50,56,62,42,54,59,35,35,32,31,37,43,48,47,38,71,56,53;51,25,36,54,47,71,53,59,41,42,57,50,38,31,27,33,26,40,42,31,25;26,47,26,37,42,15,60,40,43,48,30,25,52,28,41,40,34,28,41,38,40,30,35,27,27,32,44,31;32,29,31,25,21,23,25,39,33,21,36,21,14,23,33,27;31,16,23,21,13,20,40,13,27,33,34,31,13,40,58,24;24,17,18,18,21,18,16,24,15,18,33,21,14;24,21,29,31,26,18;23,22,21,32,33,24;30,30,21,23;29,23,25,18;10,20,13,18,28;12,17,18;20,15,16,16,25,21;18,26,17,22;16,15,15;25;14,18,19,16,14,20,28,13,28,39,40,29,25;27,26,18,17,20;25,25,22,19,14;21,22,18;10,29,24,21,21;13;14;25;20,29,22,11,14,17,17,13,21,11,19,17,18,20,8,21,18,24,21,15,27,21"
VERSES = [list(map(int, b.split(","))) for b in _VERSES.split(";")]
VERSES_PER_MINUTE = 10.4    # calibrated against Logos's own reading-time estimates
POSITIONS_PER_MINUTE = 1475  # ditto, for book text ranges


def _verses(book):
    if 1 <= book <= 39:
        return VERSES[book - 1]
    if 61 <= book <= 87:
        return VERSES[book - 61 + 39]
    return None


def reference_verse_count(ref):
    """Approximate number of verses in a Logos reference like 'bible+esv.24.5.1-24.7.29'."""
    try:
        body = ref.split(".", 1)[1]
        parts = [list(map(int, p.split("."))) for p in body.split("-")]
    except (IndexError, ValueError):
        return None
    a, b = parts[0], parts[-1]
    total = 0
    for book in range(a[0], b[0] + 1):
        vs = _verses(book)
        if vs is None:
            continue
        c0 = a[1] if book == a[0] and len(a) > 1 else 1
        c1 = b[1] if book == b[0] and len(b) > 1 else len(vs)
        for ch in range(c0, min(c1, len(vs)) + 1):
            v0 = a[2] if book == a[0] and len(a) > 2 and ch == a[1] else 1
            v1 = b[2] if book == b[0] and len(b) > 2 and ch == b[1] else vs[ch - 1]
            total += max(0, v1 - v0 + 1)
    return total


def text_range_positions(tr):
    """Approximate length of a reading-plan textRange, in Logos position units."""
    tr = urllib.parse.unquote(urllib.parse.unquote(tr or ""))
    m = re.search(r"\?len=(\d+)", tr)
    if m:
        return int(m.group(1))
    start = re.search(r"StartPosition=Article=([^|]+)\|ArticleLength=(\d+)\|.*?Offset=(\d+)", tr, re.S)
    end = re.search(r"EndPosition=Article=([^|]+)\|ArticleLength=(\d+)\|.*?Offset=(\d+)", tr, re.S)
    if not start or not end:
        return None
    if start.group(1) == end.group(1):
        return int(end.group(3)) - int(start.group(3))
    # Only adjacent articles (CH1→CH2, R14.A1→R15.A1) can be measured: the lengths of
    # any articles in between aren't stored.
    a = list(map(int, re.findall(r"\d+", start.group(1))))
    b = list(map(int, re.findall(r"\d+", end.group(1))))
    diffs = [y - x for x, y in zip(a, b) if x != y]
    if len(a) != len(b) or diffs != [1]:
        return None
    return int(start.group(2)) - int(start.group(3)) + int(end.group(3))


def short_reference(ref):
    full = format_reference(ref)
    if not full:
        return None
    for num, name in sorted(BOOKS.items(), key=lambda kv: -len(kv[1])):
        full = re.sub(rf"(^|\u2013){re.escape(name)}(?= |$|\u2013)",
                      lambda m, n=num: m.group(1) + BOOK_ABBR[n], full)
    return full


def due_label(due, today):
    """Logos-style 'Yesterday' / 'Last week' / '2 months ago' for an overdue session."""
    days = (today - due).days
    if days <= 0:
        return ""
    if days == 1:
        return "Yesterday"
    months = (today.year - due.year) * 12 + today.month - due.month
    if months >= 2:
        return f"{months} months ago"
    if today.isocalendar()[:2] == due.isocalendar()[:2]:
        return f"{days} days ago"
    weeks = (today - today.weekday() * datetime.timedelta(days=1)
             - (due - due.weekday() * datetime.timedelta(days=1))).days // 7
    if weeks <= 1:
        return "Last week"
    if months == 1:
        return "Last month"
    return f"{weeks} weeks ago"


def streak_days(completed_dates, today):
    days = set()
    for d in completed_dates:
        try:
            days.add(datetime.datetime.fromisoformat(d).date())
        except ValueError:
            pass
    day = today if today in days else today - datetime.timedelta(days=1)
    n = 0
    while day in days:
        n += 1
        day -= datetime.timedelta(days=1)
    return n


_BOOK_ALIASES = {
    1: "gen ge gn", 2: "exod exo ex", 3: "lev le lv", 4: "num nu nm nb", 5: "deut deu dt de",
    6: "josh jos", 7: "judg jdg jg", 8: "ruth ru rth", 9: "1sam 1sa 1sm", 10: "2sam 2sa 2sm",
    11: "1kgs 1ki 1kin", 12: "2kgs 2ki 2kin", 13: "1chr 1ch 1chron", 14: "2chr 2ch 2chron",
    15: "ezra ezr", 16: "neh ne", 17: "esth est es", 18: "job jb",
    19: "psalms psalm ps psa pss psm", 20: "prov pro prv pr", 21: "eccl ecc ec qoh",
    22: "songofsongs songofsolomon song sos canticles ss", 23: "isa is", 24: "jer je jr",
    25: "lam la", 26: "ezek eze ezk", 27: "dan da dn", 28: "hos ho", 29: "joel jl joe",
    30: "amos am", 31: "obad ob", 32: "jonah jon jnh", 33: "mic mi", 34: "nah na",
    35: "hab hb", 36: "zeph zep zp", 37: "hag hg", 38: "zech zec zc", 39: "mal ml",
    61: "matt mt", 62: "mark mk mrk mar", 63: "luke lk luk", 64: "john jn jhn joh",
    65: "acts ac act", 66: "rom ro rm", 67: "1cor 1co", 68: "2cor 2co", 69: "gal ga",
    70: "eph ephes", 71: "phil php pp", 72: "col", 73: "1thess 1th 1thes", 74: "2thess 2th 2thes",
    75: "1tim 1ti", 76: "2tim 2ti", 77: "titus tit", 78: "phlm phm philem", 79: "heb",
    80: "jas jm", 81: "1pet 1pe 1pt", 82: "2pet 2pe 2pt", 83: "1jn 1jo 1jhn", 84: "2jn 2jo 2jhn",
    85: "3jn 3jo 3jhn", 86: "jude jud jd", 87: "rev re rv revelations apocalypse",
}


def _book_lookup():
    table = {}
    for num, name in BOOKS.items():
        table[re.sub(r"\s+", "", name.lower())] = num
        table[re.sub(r"\s+", "", BOOK_ABBR[num].lower())] = num
    table["psalms"] = 19
    for num, aliases in _BOOK_ALIASES.items():
        for a in aliases.split():
            table[a] = num
    return table


BOOK_LOOKUP = _book_lookup()
_ORDINALS = {"i": "1", "ii": "2", "iii": "3", "first": "1", "second": "2", "third": "3",
             "1st": "1", "2nd": "2", "3rd": "3"}
_REF_RE = re.compile(
    r"(?<![\w])((?:(?:[123]|i{1,3}|1st|2nd|3rd|first|second|third)\s*)?[a-z][a-z ]{0,20}?[a-z])\.?\s*"
    r"(\d{1,3})(?:\s*[:.v]\s*(\d{1,3})(?:\s*[-\u2013\u2014]\s*(\d{1,3})(?:\s*[:.]\s*(\d{1,3}))?)?"
    r"|\s*[-\u2013\u2014]\s*(\d{1,3}))?(?![\w:])", re.I)


def split_reference(text):
    """'passage john 3:16' → ('John 3:16', 'passage'): a reference typed at the end of a
    query, and the words before it. Lowercase abbreviations count here (typed on purpose)."""
    words = (text or "").split()

    def single(ws):
        t = " ".join(ws)
        ms = list(_REF_RE.finditer(t))
        if len(ms) != 1 or ms[0].start() != 0 or ms[0].end() != len(t):
            return ""
        r = find_references(t, loose=True)
        return r[0] if len(r) == 1 else ""

    for i in range(len(words)):
        ref = single(words[i:])
        if ref:  # drop leading words the regex took as part of the book while the reference stays
            while i + 1 < len(words) and single(words[i + 1:]) == ref:
                i += 1
            return ref, " ".join(words[:i])
    return "", text


def find_references(text, loose=False):
    """Bible references in free text → ['John 3:16', '1 Corinthians 13:4-7', …] (in order)."""
    out = []
    text = text or ""
    pos = 0
    while True:
        m = _REF_RE.search(text, pos)
        if not m:
            break
        pos = m.end()
        raw, ch, v1, v2, v3, ch2 = m.groups()
        words = raw.split()
        # try the longest tail of the matched words that names a book ("for God so loved…
        # (John" → "john"), keeping a leading ordinal ("1 Cor", "First John").
        num = None
        for i in range(len(words)):
            cand = words[i:]
            if cand and cand[0].lower() in _ORDINALS:
                cand = [_ORDINALS[cand[0].lower()]] + cand[1:]
            key = "".join(cand).lower()
            if key in BOOK_LOOKUP:
                tail = " ".join(words[i:])
                # short abbreviations only count when capitalised ("is 5" isn't Isaiah)
                letters = re.sub(r"[^a-z]", "", key)
                if len(letters) <= 3 and not loose and not tail.lstrip("123 ")[:1].isupper():
                    continue
                num = BOOK_LOOKUP[key]
                break
        if num is None:
            # not a book: the number may start the next reference ("cf. 1 Pet 2:24")
            pos = m.start(2)
            continue
        if loose and not v1 and not ch2:
            # a typed or selected reference can separate chapter and verse with a space ("John 1 10")
            sp = re.match(r"\s+(\d{1,3})(?![\w:])", text[m.end():])
            if sp:
                v1 = sp.group(1)
                pos = m.end() + sp.end()
        ref = f"{BOOKS[num]} {ch}"
        if v1:
            ref += f":{v1}"
            if v2:
                ref += f"-{v2}" + (f":{v3}" if v3 else "")
        elif ch2:
            ref += f"-{ch2}"
        out.append(ref)
    return out


def notify(summary, body="", icon="logos-plasma", actions=(), bus=None, timeout=-1):
    """Send a desktop notification; returns its id (0 on failure)."""
    import dbus
    try:
        bus = bus or dbus.SessionBus()
        n = dbus.Interface(bus.get_object("org.freedesktop.Notifications",
                                          "/org/freedesktop/Notifications"),
                           "org.freedesktop.Notifications")
        return int(n.Notify("Logos", 0, icon, summary, body, dbus.Array(actions, signature="s"),
                            dbus.Dictionary({"desktop-entry": "logos-plasma"}, signature="sv"),
                            timeout))
    except Exception as e:
        log(f"notification failed: {e}")
        return 0


def format_reference(ref, dash="\u2013"):
    """Logos datatype reference → readable text.
    'bible+esv.24.5.1-24.7.29' → 'Jeremiah 5:1–7:29'; 'bible+esv.20.25.1-20.25.4' → 'Proverbs 25:1–4'.
    Returns None if it can't be parsed (e.g. deuterocanon numbering)."""
    try:
        body = ref.split(".", 1)[1]
        parts = [list(map(int, p.split("."))) for p in body.split("-")]
    except (IndexError, ValueError):
        return None

    def one(p, book=True):
        name = BOOKS.get(p[0])
        if name is None:
            raise KeyError(p[0])
        loc = ":".join(map(str, p[1:]))
        return (f"{name} {loc}" if loc else name) if book else loc

    try:
        start = one(parts[0])
        if len(parts) == 1:
            return start
        a, b = parts
        if a[0] != b[0]:
            return f"{start}{dash}{one(b)}"
        if len(a) == 3 and len(b) == 3 and a[1] == b[1]:
            return f"{start}{dash}{b[2]}"
        return f"{start}{dash}{one(b, book=False)}"
    except KeyError:
        return None


def dotnet_guid(blob):
    """ScheduleId blobs are .NET GUID byte order; statuses store the plain hex form."""
    if not blob or len(blob) != 16:
        return None
    b = bytes(blob)
    return (b[3::-1] + b[5:3:-1] + b[7:5:-1] + b[8:]).hex()


@dataclass
class Resource:
    record_id: int
    resource_id: str
    logosres: str
    abbr: str
    title: str
    use: int = 0
    rank: int = 0  # Logos prioritization; 0 = not prioritized
    langs: str = ""  # lexicons: "g", "h", "gh" or "" (unknown)

    @property
    def key(self):
        return norm(self.abbr)


def find_logos_dirs(override=""):
    """Return (Data/<user>, Documents/<user>) for the Logos/Verbum install."""
    candidates = []
    if override:
        candidates = [Path(override).expanduser()]
    else:
        roots = []
        for cfg in glob.glob(str(XDG_DATA / "FaithLife-Community" / "*" / "*.json")):
            try:
                inst = json.load(open(cfg)).get("install_dir")
                if inst:
                    roots.append(Path(inst))
            except Exception:
                pass
        roots += [Path(p) for p in glob.glob(str(XDG_DATA / "FaithLife-Community" / "*"))]
        roots += [Path(p) for p in glob.glob(str(HOME / "*Bible*")) + glob.glob(str(HOME / "Verbum*"))]
        for r in roots:
            for prod in ("Logos", "Verbum"):
                candidates += [Path(p) for p in glob.glob(
                    str(r / "data" / "*" / "drive_c" / "users" / "*" / "AppData" / "Local" / prod))]
    best = None
    for base in candidates:
        for cat in glob.glob(str(base / "Data" / "*" / "LibraryCatalog" / "catalog.db")):
            m = os.path.getmtime(cat)
            if best is None or m > best[0]:
                user = Path(cat).parent.parent
                best = (m, user, base / "Documents" / user.name)
    return (best[1], best[2]) if best else (None, None)


def ro_connect(path):
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=1)


class Library:
    REFRESH = 30  # seconds between freshness checks

    def __init__(self):
        self.data_dir = self.docs_dir = None
        self.bibles: list[Resource] = []
        self.by_key: dict[str, Resource] = {}
        self.lexicons: list[Resource] = []
        self._checked = 0
        self._stamp = None
        self._db = None
        self._covers = {}
        self.error = None

    @property
    def catalog_path(self):
        return self.data_dir / "LibraryCatalog" / "catalog.db" if self.data_dir else None

    def refresh(self, override=""):
        now = time.monotonic()
        if now - self._checked < self.REFRESH and self._stamp is not None:
            return
        self._checked = now
        if self.data_dir is None:
            self.data_dir, self.docs_dir = find_logos_dirs(override)
            if self.data_dir is None:
                self.error = "Logos library catalog not found"
                return
        files = [self.catalog_path, Path(str(self.catalog_path) + "-wal"),
                 self.data_dir / "KeyLinkManager" / "keylinkmanager.db-wal",
                 self.docs_dir / "KeyLinkManager" / "KeyLinkSyncManager.db"]
        stamp = tuple(f.stat().st_mtime if f.exists() else 0 for f in files)
        if stamp == self._stamp:
            return
        try:
            self._load()
            self._stamp, self.error = stamp, None
        except Exception as e:
            self.error = f"reading Logos catalog failed: {e}"
            log(self.error)

    def db(self):
        if self._db is None:
            self._db = ro_connect(self.catalog_path)
        return self._db

    def _load(self):
        if self._db is not None:
            self._db.close()
            self._db = None
        ranks, self.keylink_lang = self._load_priorities()
        rows = self.db().execute("""
            SELECT r.RecordId, r.ResourceId,
                   coalesce(nullif(r.UserAbbreviatedTitle, ''), r.AbbreviatedTitle),
                   coalesce(nullif(r.UserTitle, ''), r.Title), r.UseCount,
                   (SELECT group_concat(AlternateResourceId, ' ') FROM AlternateResourceIds a
                    WHERE a.RecordId = r.RecordId)
            FROM Records r
            WHERE r.Type = 'text.monograph.bible' AND r.Availability >= 1""").fetchall()
        bibles = []
        for rec, rid, abbr, title, use, alts in rows:
            if not abbr:
                continue
            bibles.append(Resource(rec, rid, logosres_id(rid, alts), abbr, title,
                                   use or 0, ranks.get(rid, 0)))
        # When two Bibles share an alias key ("NASB95" vs "NASB 95" para edition), prefer an
        # exact abbreviation, then the prioritized / most used one.
        bibles.sort(key=lambda b: (b.abbr.lower() != b.key, priority_key(b), len(b.title)))
        self.bibles = bibles
        self.by_key = {}
        for b in bibles:
            self.by_key.setdefault(b.key, b)
        self.lexicons = self._load_lexicons(ranks)
        log(f"catalog: {len(bibles)} Bibles, {len(self.lexicons)} lexicons from {self.catalog_path}")

    def _load_priorities(self):
        """Logos's Prioritize list: {ResourceId: rank}, where a LOWER rank is HIGHER priority.

        Data/<user>/KeyLinkManager/keylinkmanager.db holds the ranks Logos actually uses;
        the synced copy in Documents/ is a fallback (same direction, older values)."""
        queries = [
            (self.data_dir / "KeyLinkManager" / "keylinkmanager.db",
             "SELECT r.ResourceId, k.Rank, k.Language, k.DataType, k.SourceResourceId "
             "FROM KeyLinkRules k JOIN Resources r ON r.Id = k.Resource"),
            (self.docs_dir / "KeyLinkManager" / "KeyLinkSyncManager.db",
             "SELECT ResourceId, Rank, Language, DataType, SourceResourceId FROM KeyLinkRules "
             "WHERE IsDeleted = 0 AND ResourceId IS NOT NULL"),
        ]
        for path, sql in queries:
            if not path.exists():
                continue
            try:
                ranks, langs = {}, {}
                with ro_connect(path) as c:
                    for rid, rank, lang, dtype, source in c.execute(sql):
                        rank = int(rank)
                        # A rule scoped to Greek/Hebrew data or to the LXX tells us the language.
                        if not lang and dtype:
                            lang = "el" if dtype.endswith("+g") else "he" if dtype.endswith("+h") else None
                        if not lang and source and "LXX" in source.upper():
                            lang = "el"
                        if rid not in ranks or rank < ranks[rid]:
                            ranks[rid] = rank
                        if lang:
                            langs[rid] = lang
                if ranks:
                    return ranks, langs
            except sqlite3.Error as e:
                log(f"prioritization {path.name}: {e}")
        return {}, {}

    def _load_lexicons(self, ranks):
        rows = self.db().execute("""
            SELECT r.RecordId, r.ResourceId,
                   coalesce(nullif(r.UserAbbreviatedTitle, ''), r.AbbreviatedTitle),
                   coalesce(nullif(r.UserTitle, ''), r.Title), r.UseCount,
                   (SELECT group_concat(AlternateResourceId, ' ') FROM AlternateResourceIds a
                    WHERE a.RecordId = r.RecordId),
                   (SELECT group_concat(t.Value, ' ') FROM RecordTraits rt
                    JOIN Traits t ON t.TraitId = rt.TraitId WHERE rt.RecordId = r.RecordId)
            FROM Records r
            WHERE r.Type LIKE 'text.monograph.lexicon%' AND r.Availability >= 1""").fetchall()
        greek = {"supports-strongs+g", "supports-gk+g", "supports-dbl+g"}
        hebrew = {"supports-strongs+h", "supports-gk+h", "supports-bdb", "supports-dbl+h"}
        lex = []
        for rec, rid, abbr, title, use, alts, traits in rows:
            t = set((traits or "").split())
            kl = self.keylink_lang.get(rid, "")
            if kl in ("el", "grc"):
                langs = "g"
            elif kl in ("he", "hbo", "arc"):
                langs = "h"
            else:
                langs = ("g" if t & greek else "") + ("h" if t & hebrew else "")
            lex.append(Resource(rec, rid, logosres_id(rid, alts), abbr or "", title, use or 0,
                                ranks.get(rid, 0), langs))
        lex.sort(key=priority_key)
        return lex

    def lexicon_picker(self, word, size):
        """Prioritized lexicons for the script typed: Greek or Hebrew."""
        if re.search(r"[\u0590-\u05ff]", word):
            want = "h"
        elif re.search(r"[\u0370-\u03ff\u1f00-\u1fff]", word):
            want = "g"
        else:
            want = ""
        pool = [l for l in self.lexicons if l.rank or l.use]
        pool = [l for l in pool if not want or want in l.langs or not l.langs]
        return pool[:size]

    def picker(self, names, order, size):
        if names:
            chosen = [self.by_key[norm(n)] for n in names if norm(n) in self.by_key]
            return chosen[:size] if size else chosen
        if order == "usage":
            pool = sorted(self.bibles, key=lambda b: b.use, reverse=True)
        else:  # prioritized first (Logos's "Top Bibles"), then most used
            pool = sorted(self.bibles, key=priority_key)
        return pool[:size]

    def search_titles(self, words, limit=8):
        sql = ["SELECT r.RecordId, r.ResourceId, r.AbbreviatedTitle, r.Title, r.UseCount,"
               " (SELECT group_concat(AlternateResourceId, ' ') FROM AlternateResourceIds a"
               "  WHERE a.RecordId = r.RecordId)"
               " FROM Records r WHERE r.Availability >= 1"
               " AND r.ResourceId NOT LIKE 'RVI:%' AND r.Type NOT LIKE 'lbx.reverse-interlinear%'"]
        args = []
        for w in words:
            sql.append(" AND (r.Title || ' ' || r.AbbreviatedTitle || ' ' || r.Authors"
                       " || ' ' || coalesce(r.UserTitle, '')) LIKE ?")
            args.append(f"%{w}%")
        q = " ".join(words).lower()
        sql.append(" ORDER BY lower(r.AbbreviatedTitle) = ? DESC, r.UseCount DESC,"
                   " r.LastAccessedUtc DESC LIMIT ?")
        args += [q, limit]
        out = []
        for rec, rid, abbr, title, use, alts in self.db().execute("".join(sql), args):
            out.append(Resource(rec, rid, logosres_id(rid, alts), abbr or "", title, use or 0))
        return out

    # Reading plans ----------------------------------------------------------
    def logosres_for(self, resource_id):
        row = self.db().execute(
            "SELECT r.ResourceId, (SELECT group_concat(AlternateResourceId, ' ') FROM "
            "AlternateResourceIds a WHERE a.RecordId = r.RecordId) FROM Records r "
            "WHERE r.ResourceId = ?", (resource_id,)).fetchone()
        return logosres_id(*row) if row else resource_id.split(":", 1)[-1].lower()

    def reading_plans(self, open_url, today=None):
        """Active plans with their next unread session, most recently used first."""
        today = today or datetime.date.today()
        path = self.docs_dir / "Documents" / "ReadingPlan" / "ReadingPlan.db" if self.docs_dir else None
        if not path or not path.exists():
            return []
        with ro_connect(path) as c:
            docs = {}
            for title, sched, sessions in c.execute(
                    "SELECT Title, ScheduleId, Sessions FROM ReadingPlanDocuments WHERE IsDeleted = 0"):
                g = dotnet_guid(sched)
                if g:
                    docs[g] = (title, sessions)
            statuses = c.execute(
                "SELECT SyncId, ReadSessions, ModifiedDate, SessionsMetadata, "
                "coalesce(IsArchived, 0), NotificationTime FROM ReadingPlanStatus WHERE IsDeleted = 0 "
                "ORDER BY ModifiedDate DESC").fetchall()
        # Plans you've used (most recent first), then plans never started (no status row).
        seen = {row[0] for row in statuses}
        rows = [r[:4] + (r[5],) for r in statuses if not r[4]]
        rows += [(g, None, "", None, None) for g in docs if g not in seen]
        out = []
        for sync_id, read, modified, meta, notify_time in rows:
            if sync_id not in docs:
                continue
            title, sessions = docs[sync_id]
            try:
                sessions = json.loads(sessions or "[]")
            except ValueError:
                continue
            done = set()
            for part in (read or "").split(","):
                if part:
                    a, _, b = part.partition("-")
                    done.update(range(int(a), int(b or a) + 1))
            nxt = next((i for i in range(len(sessions)) if i not in done), None)
            if nxt is None:
                continue  # finished
            sess = sessions[nxt]
            readings = []
            minutes = 0.0
            unknown_time = False
            for group in sess.get("readings", []):
                for r in group:
                    rid = r.get("resourceId", "")
                    lres = self.logosres_for(rid) if rid else ""
                    if r.get("reference"):
                        minutes += (reference_verse_count(r["reference"]) or 0) / VERSES_PER_MINUTE
                    elif r.get("textRange"):
                        n_pos = text_range_positions(r["textRange"])
                        if n_pos is None:
                            unknown_time = True
                        else:
                            minutes += n_pos / POSITIONS_PER_MINUTE
                    if r.get("reference"):
                        short = short_reference(r["reference"])
                        label = format_reference(r["reference"]) or r["reference"]
                        url = open_url.replace("{logosres}", lres).replace(
                            "{q}", encode(label.replace("\u2013", "-"), ":,."))
                    else:
                        label = sess.get("title") or title
                        short = None
                        url = f"logosres:{lres}"
                    avail = self.db().execute("SELECT Availability FROM Records WHERE ResourceId = ?",
                                              (rid,)).fetchone() if rid else None
                    readings.append({"label": label, "short": short, "url": url, "resourceId": rid,
                                     "cloud": bool(avail and avail[0] == 1)})
            date = sess.get("date", "")
            behind = None
            try:
                d = datetime.date.fromisoformat(date)
                if d.year > 1900:  # template plans use 1900-01-01 placeholders
                    behind = (today - d).days
            except ValueError:
                pass
            try:
                completed = [v.get("completedDate", "") for v in json.loads(meta or "{}").values()]
            except (ValueError, AttributeError):
                completed = []
            shorts = [r["short"] for r in readings if r["short"]]
            n = len(readings)
            out.append({
                "title": title, "session": nxt + 1, "total": len(sessions), "done": len(done),
                "progress": len(done) / len(sessions) if sessions else 0,
                "date": date, "behind": behind, "lastActivity": modified,
                "kind": "today" if behind is not None else "anytime",
                "dueLabel": due_label(datetime.date.fromisoformat(date), today) if behind else "",
                "streak": streak_days(completed, today),
                "minutes": None if unknown_time or not minutes else max(1, round(minutes)),
                "summary": ", ".join(shorts) if shorts else (f"{n} reading" if n == 1 else f"{n} readings"),
                "sessionTitle": sess.get("title", ""),
                "coverResource": next((r["resourceId"] for r in readings if r["resourceId"]), ""),
                "notificationTime": notify_time or "",
                "readings": readings})
        return out

    # Devotionals, Factbook, history ---------------------------------------------
    def devotionals(self, names=()):
        rows = self.db().execute("""
            SELECT r.RecordId, r.ResourceId, coalesce(nullif(r.UserAbbreviatedTitle, ''), r.AbbreviatedTitle),
                   coalesce(nullif(r.UserTitle, ''), r.Title), r.UseCount,
                   (SELECT group_concat(AlternateResourceId, ' ') FROM AlternateResourceIds a
                    WHERE a.RecordId = r.RecordId)
            FROM Records r WHERE r.Type = 'lbx.calendar-devotional' AND r.Availability >= 1""").fetchall()
        ranks, _ = self._load_priorities()
        devs = [Resource(rec, rid, logosres_id(rid, alts), abbr or "", title, use or 0, ranks.get(rid, 0))
                for rec, rid, abbr, title, use, alts in rows]
        devs.sort(key=priority_key)
        if names:
            wanted = [n.lower() for n in names]
            return [d for w in wanted for d in devs if w in (d.title.lower(), d.abbr.lower())]
        return devs

    def default_devotionals(self, names=()):
        """The devotionals to feature: configured ones, else prioritized, else the most used."""
        devs = self.devotionals(names)
        if names:
            return devs
        pri = [d for d in devs if d.rank]
        return pri[:2] if pri else [d for d in devs[:1] if d.use]

    def factbook(self, text, limit=8):
        """Factbook entries matching the words typed, ranked the way Logos does: an exact
        name (or alternative name) first, then by how often the Bible mentions the entry."""
        path = self.data_dir / "AutoComplete" / "AutoComplete.db" if self.data_dir else None
        words = [w for w in re.findall(r"\w+", text.lower()) if w]
        if not path or not path.exists() or not words:
            return []
        query = " ".join(words)
        first, rest = words[0], words[1:]
        having = "".join(" AND group_concat(lower(l.LabelText), '|') LIKE ?" for _ in rest)
        with ro_connect(path) as c:
            rows = c.execute(f"""
                SELECT t.TermId, t.Reference, ik.IconKind,
                       max(lower(l.LabelText) = ?) AS exact,
                       (SELECT count(*) FROM MentionReferences m WHERE m.TermId = t.TermId) AS mentions
                FROM LabelWords w JOIN Labels l ON l.LabelId = w.LabelId
                JOIN Terms t ON t.TermId = l.TermId
                LEFT JOIN IconKinds ik ON ik.IconKindId = t.IconKindId
                WHERE w.LanguageId = 1 AND w.FoldedText >= ? AND w.FoldedText < ? AND l.LanguageId = 1
                GROUP BY t.TermId HAVING 1 {having}
                ORDER BY exact DESC, mentions DESC, t.Reference LIKE 'bk.#%' DESC, t.Reference LIKE 'bio.%'
                LIMIT ?""", (query, first, first + "\uffff", *[f"%{w}%" for w in rest], limit)).fetchall()
            out = []
            for term_id, ref, kind, exact, mentions in rows:
                primary = c.execute("SELECT LabelText FROM Labels WHERE TermId = ? AND IsPrimary = 1 "
                                    "AND LanguageId = 1", (term_id,)).fetchone()
                desc = c.execute("SELECT Description FROM Descriptions WHERE TermId = ? AND LanguageId = 1",
                                 (term_id,)).fetchone()
                name = primary[0] if primary else ref
                # show the alternative name that matched when it differs from the main name
                alias = ""
                if name.lower() != query:
                    hit = c.execute("SELECT LabelText FROM Labels WHERE TermId = ? AND LanguageId = 1 "
                                    "AND lower(LabelText) = ?", (term_id, query)).fetchone()
                    alias = hit[0] if hit else ""
                out.append({"key": ref, "kind": kind or "", "label": name, "alias": alias,
                            "description": (desc[0] if desc else "") or "", "mentions": mentions})
        return out

    def layouts(self):
        """Your saved layouts' names, as in Logos's Layouts menu (no autosaves)."""
        path = self.docs_dir / "LayoutManager" / "layouts.db" if self.docs_dir else None
        if not path or not path.exists():
            return []
        with ro_connect(path) as db:
            rows = db.execute("SELECT Title, MAX(CreatedDate) FROM Layouts WHERE IsDeleted = 0 "
                              "AND Title <> '' AND Title <> 'Application Closed' GROUP BY Title").fetchall()
        return sorted((r[0] for r in rows), key=str.casefold)

    def recent(self, open_url, limit=10):
        path = self.data_dir / "HistoryManager" / "history.db" if self.data_dir else None
        if not path or not path.exists():
            return []
        with ro_connect(path) as c:
            rows = c.execute("SELECT Title, Subtitle, Bookmark FROM History WHERE IsDeleted = 0 "
                             "AND Bookmark LIKE 'Resource|%' ORDER BY LastVisited DESC LIMIT 300").fetchall()
        seen, out = set(), []
        for title, subtitle, bm in rows:
            fields = dict(kv.split("=", 1) for kv in bm.split("|")[1:] if "=" in kv)
            rid = fields.get("Id", "")
            if not rid or rid in seen:
                continue
            seen.add(rid)
            lres = self.logosres_for(rid)
            ref = urllib.parse.unquote(fields.get("Reference", ""))
            hw = urllib.parse.unquote(fields.get("Headword", ""))
            if ref.startswith("bible") and format_reference(ref):
                url = open_url.replace("{logosres}", lres).replace(
                    "{q}", encode(format_reference(ref).replace("\u2013", "-"), ":,."))
            elif hw:
                url = f"logosres:{lres};hw={encode(hw, '')}"
            else:
                url = f"logosres:{lres}"
            out.append({"title": title, "subtitle": subtitle or "", "url": url, "resourceId": rid})
            if len(out) >= limit:
                break
        return out

    def sermon_passage(self, today=None):
        """(title, date, datatype reference) for your next sermon, or the latest one.
        The date comes from the sermon's date field, else a dd/mm/yy date in its title."""
        today = today or datetime.date.today()
        path = self.docs_dir / "Documents" / "Sermon" / "Sermon.db" if self.docs_dir else None
        if not path or not path.exists():
            return None
        with ro_connect(path) as c:
            docs = c.execute("SELECT Id, Title, Date, ModifiedDate, OccasionsJson FROM Documents "
                             "WHERE IsDeleted = 0 AND coalesce(IsTemplate, 0) = 0").fetchall()
            dated = []
            for did, title, date, modified, occasions in docs:
                d = None
                # Occasions ("when and where it's preached") carry the real dates; a sermon
                # can have several, so use the next one, else the latest.
                try:
                    occ = sorted(datetime.date.fromisoformat(o["date"][:10])
                                 for o in json.loads(occasions or "[]") if o.get("date"))
                except (ValueError, TypeError, AttributeError):
                    occ = []
                if occ:
                    d = next((x for x in occ if x >= today), occ[-1])
                if d is None and date:
                    try:
                        d = datetime.date.fromisoformat(str(date)[:10])
                    except ValueError:
                        pass
                if d is None and not occ:
                    m = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})\b", title or "")
                    if m:
                        dd, mm, yy = map(int, m.groups())
                        try:
                            d = datetime.date(yy + 2000 if yy < 100 else yy, mm, dd)
                        except ValueError:
                            d = None
                dated.append((d, modified or "", did, title or ""))
            # newest edit first, then by date (stable), so ties go to the most recently edited
            by_edit = sorted(dated, key=lambda x: x[1], reverse=True)
            upcoming = sorted([x for x in by_edit if x[0] and x[0] >= today], key=lambda x: x[0])
            past = sorted([x for x in by_edit if x[0] and x[0] < today], key=lambda x: x[0], reverse=True)
            latest = sorted(dated, key=lambda x: x[1], reverse=True)
            for d, _, did, title in (upcoming[:1] + past[:1] + latest[:1]):
                ref = None
                for (pj,) in c.execute("SELECT PassageJson FROM Blocks WHERE DocumentId = ? AND IsDeleted = 0 "
                                       "AND PassageJson IS NOT NULL ORDER BY Rank", (did,)):
                    try:
                        ref = json.loads(pj)["reference"]["raw"]
                        break
                    except (ValueError, KeyError, TypeError):
                        continue
                if not ref:
                    found = find_references(re.sub(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", "", title))
                    if found:
                        ref = found[0]  # readable form, e.g. "Genesis 4:17-26"
                if ref:
                    return {"title": title, "date": d.isoformat() if d else "", "reference": ref}
        return None

    def sermon_commentaries(self, sermon, count=3, open_url=""):
        """Your own 4–5★ commentaries covering the sermon passage (or, if you've rated none,
        the best community-rated ones), each linking straight to the passage."""
        ref = sermon["reference"]
        readable = format_reference(ref) if ref.startswith("bible") else ref
        if ref.startswith("bible"):
            datatype_ref = ref
        else:  # "Genesis 4:17-26" → find book number for coverage checks
            m = re.match(r"(.+?) (\d+)(?::(\d+))?", ref)
            num = BOOK_LOOKUP.get(re.sub(r"\s+", "", m.group(1).lower())) if m else None
            datatype_ref = f"bible.{num}.{m.group(2)}.{m.group(3) or 1}" if num else ""
        if not datatype_ref or not readable:
            return []
        rows = self.db().execute("""
            SELECT r.RecordId, r.ResourceId, r.Title, r.Authors, r.ReferenceSupersets, r.UserRating,
                   r.CommunityRating, r.CommunityRatingCount, r.Availability,
                   (SELECT group_concat(AlternateResourceId, ' ') FROM AlternateResourceIds a
                    WHERE a.RecordId = r.RecordId)
            FROM Records r WHERE r.Type = 'text.monograph.commentary.bible' AND r.Availability IN (1, 2)""").fetchall()
        hits = [r for r in rows if covers(r[4], datatype_ref)]
        mine = sorted([r for r in hits if (r[5] or 0) >= 4], key=lambda r: (-r[5], -(r[6] or 0) * (r[7] or 0)))
        rest = sorted([r for r in hits if (r[5] or 0) < 4 and (r[7] or 0) >= 15],
                      key=lambda r: -((r[6] or 0) * r[7] + 3.6 * 30) / (r[7] + 30))
        # your own 4–5★ ratings only; community ratings only when you've rated none for it
        rest = [] if mine else rest[:3]
        q = encode(readable.replace("\u2013", "-"), ":,.")
        out, seen = [], set()
        for rec, rid, title, authors, _, mine_rating, rating, n, avail, alts in mine + rest:
            key = (title.casefold(), (authors or "").casefold())
            if key in seen:  # same book listed twice in the catalog (e.g. two editions/records)
                continue
            seen.add(key)
            if len(out) >= count:
                break
            out.append({"title": title, "authors": byline(authors or ""), "rating": round(rating or 0, 1),
                        "ratings": n or 0, "myRating": mine_rating or 0, "resourceId": rid,
                        "url": f"logosres:{logosres_id(rid, alts)};ref=Bible.{q}",
                        "cover": self.cover_file(rid), "cloud": avail == 1,
                        "sermon": {"title": sermon["title"], "passage": readable, "date": sermon["date"]}})
        return out

    def showcase(self, count=12, seed=None, min_ratings=15):
        """Well-rated books you own but haven't read, one per series/author, rotating daily.
        Books you've rated count as read (271 rated books have no reading progress: read in
        print or before progress was synced).

        "Unread" uses Logos's synced reading progress (ReadingProgressManager), so books you
        read on other devices are excluded, plus local use counts/last-accessed."""
        import random
        read = set()
        rp = self.data_dir / "ReadingProgressManager" / "readingprogressmanager.db"
        if rp.exists():
            with ro_connect(rp) as c:
                read.update(r for (r,) in c.execute(
                    "SELECT ResourceId FROM ResourceReadingProgress WHERE IsDeleted = 0"))
                read.update(r for (r,) in c.execute(
                    "SELECT ResourceId FROM ReadingStatus WHERE PercentageRead > 0"))
        keep_types = SHOWCASE_TYPES
        rows = self.db().execute(f"""
            SELECT r.RecordId, r.ResourceId, r.Title, r.Authors, r.Series, r.Type,
                   r.CommunityRating, r.CommunityRatingCount, r.Availability,
                   (SELECT group_concat(AlternateResourceId, ' ') FROM AlternateResourceIds a
                    WHERE a.RecordId = r.RecordId)
            FROM Records r JOIN Images i ON i.RecordId = r.RecordId
            WHERE r.Availability IN (1, 2) AND r.UserRating IS NULL
              AND r.Type IN ({",".join("?" * len(keep_types))})
              AND r.UseCount = 0 AND r.LastAccessed IS NULL
              AND r.CommunityRatingCount >= ? AND i.Image IS NOT NULL""",
            (*keep_types, min_ratings)).fetchall()
        # Bayesian average: books with few ratings are pulled towards the library's mean rating.
        prior = sum(r[6] * r[7] for r in rows) / max(1, sum(r[7] for r in rows))  # rating × count
        weight = 30
        scored = []
        cloud = {}
        for rec, rid, title, authors, series, typ, rating, n, avail, alts in rows:
            if rid in read:
                continue
            cloud[rid] = avail == 1
            score = (rating * n + prior * weight) / (n + weight)
            scored.append((score, rec, rid, title, authors or "", series or "", typ, rating, n, alts))
        scored.sort(reverse=True)
        # Diversity: one per series and per first author; commentaries at most a third.
        pool, series_seen, authors_seen, commentaries = [], set(), set(), 0
        for item in scored:
            _, _, _, _, authors, series, typ, *_ = item
            author = re.split(r"[\t;]", authors)[0].split(",")[0].strip().lower()
            if (series and series.lower() in series_seen) or (author and author in authors_seen):
                continue
            if typ.endswith("commentary.bible") and commentaries >= max(2, count // 3) * 4:
                continue
            series_seen.add(series.lower())
            authors_seen.add(author)
            commentaries += typ.endswith("commentary.bible")
            pool.append(item)
            if len(pool) >= count * 3:
                break
        rng = random.Random(seed if seed is not None else datetime.date.today().isoformat())
        picks, n_comm = [], 0
        for item in rng.sample(pool, len(pool)):
            if item[6].endswith("commentary.bible"):
                if n_comm >= max(1, count // 3):
                    continue
                n_comm += 1
            picks.append(item)
            if len(picks) >= count:
                break
        picks.sort(reverse=True)
        out = []
        for score, rec, rid, title, authors, series, typ, rating, n, alts in picks:
            out.append({"title": title, "authors": byline(authors), "series": series,
                        "rating": round(rating, 1), "ratings": n, "resourceId": rid,
                        "cloud": cloud.get(rid, False),
                        "url": f"logosres:{logosres_id(rid, alts)}", "cover": self.cover_file(rid)})
        return out

    def resource_for_link(self, url):
        """(title, availability) of the book a logosres: link opens, or None.
        Availability: 2 = downloaded, 1 = owned but in the cloud only."""
        m = re.match(r"logosres:([^;]+)", url or "")
        if not m:
            return None
        lres = urllib.parse.unquote(m.group(1))
        row = self.db().execute("""
            SELECT r.Title, r.Availability FROM Records r
            WHERE r.ResourceId = ? COLLATE NOCASE
               OR r.RecordId IN (SELECT RecordId FROM AlternateResourceIds
                                 WHERE AlternateResourceId IN (?, ?) COLLATE NOCASE)
            ORDER BY r.Availability DESC LIMIT 1""", (lres, lres, "lls:" + lres)).fetchone()
        return (row[0], row[1]) if row else None

    def cover_file(self, resource_id):
        """Write the resource's cover thumbnail to the cache and return its path (for widgets)."""
        if not resource_id:
            return ""
        cache = Path(os.environ.get("XDG_CACHE_HOME", HOME / ".cache")) / "logos-plasma" / "covers"
        path = cache / (re.sub(r"[^A-Za-z0-9._-]", "_", resource_id) + ".jpg")
        if path.exists():
            return str(path)
        row = self.db().execute(
            "SELECT i.Image FROM Images i JOIN Records r ON r.RecordId = i.RecordId "
            "WHERE r.ResourceId = ?", (resource_id,)).fetchone()
        if not row or not row[0]:
            return ""
        cache.mkdir(parents=True, exist_ok=True)
        path.write_bytes(row[0])
        return str(path)

    def cover_for(self, resource_id):
        row = self.db().execute("SELECT RecordId FROM Records WHERE ResourceId = ?",
                                (resource_id,)).fetchone()
        return self.cover(row[0]) if row else None

    def cover(self, record_id, height=64):
        if record_id in self._covers:
            return self._covers[record_id]
        img = None
        try:
            row = self.db().execute("SELECT Image FROM Images WHERE RecordId = ?",
                                    (record_id,)).fetchone()
            if row and row[0]:
                img = decode_image(row[0], height)
        except Exception as e:
            log(f"cover {record_id}: {e}")
        self._covers[record_id] = img
        return img


# Monographs: books you'd read, not consult (no commentaries or reference works).
SHOWCASE_TYPES = ("text.monograph", "text.monograph.systematic-theology",
                  "text.monograph.biblical-theology", "text.monograph.church-history",
                  "text.monograph.biography", "text.monograph.devotional",
                  "text.monograph.collected-work", "text.monograph.sermons", "text.monograph.lecture",
                  "text.monograph.introduction.new-testament", "text.monograph.introduction.old-testament")


def _ref_key(parts, fill):
    parts = list(parts) + [fill] * (3 - len(parts))
    return tuple(parts[:3])


def covers(supersets, ref):
    """Does a catalog ReferenceSupersets string ('bible.66.1-66.16.27\tbible+bhs.8…')
    cover the start of a Bible datatype reference ('bible+nkjv.1.4.17-1.4.26')?"""
    try:
        start = list(map(int, ref.split(".", 1)[1].split("-")[0].split(".")))
    except (IndexError, ValueError):
        return False
    p = _ref_key(start, 1)
    for rng in (supersets or "").split("\t"):
        if not rng.startswith("bible"):
            continue
        try:
            a, _, b = rng.split(".", 1)[1].partition("-")
            a = list(map(int, a.split(".")))
            b = list(map(int, (b or ".".join(map(str, a))).split(".")))
        except ValueError:
            continue
        if _ref_key(a, 0) <= p <= _ref_key(b, 999):
            return True
    return False


def byline(authors):
    """'Heiser, Michael S.\tBrown, Derek' → 'Michael S. Heiser & Derek Brown'."""
    names = [" ".join(reversed([x.strip() for x in a.split(",", 1)])) if "," in a else a.strip()
             for a in re.split(r"[\t;]", authors or "") if a.strip()]
    if not names:
        return ""
    return names[0] if len(names) == 1 else (f"{names[0]} & {names[1]}" if len(names) == 2
                                             else f"{names[0]} et al.")


def priority_key(r):
    """Sort key: prioritized resources first (lowest rank = top), then most used."""
    return (0, r.rank, -r.use) if r.rank else (1, 0, -r.use)


def logosres_id(resource_id, alternates):
    alts = (alternates or "").split()
    for a in alts:
        if not a.lower().startswith("lls:"):
            return a
    for a in alts:
        return a[4:]
    return resource_id.split(":", 1)[-1].lower()


try:
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
except Exception:  # covers are optional
    GdkPixbuf = None


def decode_image(data, height):
    if GdkPixbuf is None:
        return None
    loader = GdkPixbuf.PixbufLoader()
    loader.write(data)
    loader.close()
    pb = loader.get_pixbuf()
    w = max(1, round(pb.get_width() * height / pb.get_height()))
    pb = pb.scale_simple(w, height, GdkPixbuf.InterpType.BILINEAR)
    return (pb.get_width(), pb.get_height(), pb.get_rowstride(), pb.get_has_alpha(),
            pb.get_bits_per_sample(), pb.get_n_channels(), pb.get_pixels())


# ── Config ───────────────────────────────────────────────────────────────────

class Config:
    def __init__(self):
        self.mtime = -1
        self.aliases = dict(DEFAULTS["aliases"])
        self.settings = dict(DEFAULTS["settings"])
        self.commands = []

    def maybe_reload(self):
        try:
            mtime = CONFIG_PATH.stat().st_mtime
        except FileNotFoundError:
            mtime = None
        if mtime == self.mtime:
            return
        self.mtime = mtime
        data = {}
        if mtime is not None:
            try:
                with open(CONFIG_PATH, "rb") as f:
                    data = tomllib.load(f)
            except Exception as e:
                log(f"failed to parse {CONFIG_PATH}: {e} (keeping previous settings)")
                return
        self.aliases = {**DEFAULTS["aliases"], **data.get("aliases", {})}
        self.settings = {**DEFAULTS["settings"], **data.get("settings", {})}
        self.commands = [c for c in data.get("command", []) if c.get("alias") and c.get("url")]
        log(f"config: {len(self.commands)} custom commands")


# ── Matching ─────────────────────────────────────────────────────────────────

@dataclass
class Cmd:
    alias: str
    kind: str          # url | open | search | phrase | words | library | compare | help
    name: str
    hint: str = ""
    url: str = ""
    bible: Resource | None = None
    extra: dict = field(default_factory=dict)


def build_commands(cfg, lib):
    s, a = cfg.settings, cfg.aliases
    cmds = {}

    def add(c, override=False):
        if not c.alias:
            return
        k = c.alias.lower()
        if override or k not in cmds:
            cmds[k] = c

    for c in cfg.commands:  # user's own commands win over everything
        add(Cmd(c["alias"], "url", c.get("name", c["alias"]), c.get("hint", ""), c["url"],
                extra=c), override=True)
    builtin = [
        ("open", "Open passage", "a passage"), ("search", "Search", "words"),
        ("phrase", "Exact phrase search", "a phrase"), ("words", "Word search", "words"),
        ("library", "Open book", "a title or abbreviation"),
        ("compare", "Text Comparison", "a passage"), ("help", "Logos commands", "filter"),
        ("lexicon", "Lexicon", "a Greek or Hebrew word"), ("top", "Search Top Bibles", "words"),
        ("everything", "Search your library", "words"),
        ("plans", "Reading plans", "optional filter"),
        ("wordstudy", "Bible Word Study", "a word or lemma"),
        ("factbook", "Factbook", "a person, place, topic…"),
        ("recent", "Recently opened", "optional filter"),
        ("layout", "Open a layout", "optional filter"),
        ("copy", "Copy verses as text", "a passage"),
        ("devotional", "Today's devotional", "optional filter"),
    ]
    for kind, name, hint in builtin:
        add(Cmd(a.get(kind, ""), kind, name, hint))
    if s["bible_aliases"]:
        for b in lib.bibles:
            if a.get("open"):
                add(Cmd(a["open"] + b.key, "open", b.abbr, "a passage", bible=b))
            if a.get("search"):
                add(Cmd(a["search"] + b.key, "search", f"Search {b.abbr}", "words", bible=b))
        if a.get("open"):
            for l in lib.lexicons:
                if l.abbr:
                    add(Cmd(a["open"] + l.key, "headword", l.abbr, "a headword", bible=l))
    return cmds


def split_query(query, cmds):
    """(Cmd, argument) for the longest alias that matches, else (None, None).
    Word aliases need a space after them; punctuation aliases (' and .) don't."""
    q = query.lstrip()
    low = q.lower()
    for alias in sorted(cmds, key=len, reverse=True):
        if alias[0].isalnum():
            if low.startswith(alias + " "):
                return cmds[alias], q[len(alias) + 1:].strip()
            if low == alias:
                return cmds[alias], ""
        elif low.startswith(alias):
            return cmds[alias], q[len(alias):].strip()
    return None, None


def conflicts(cmds):
    """Aliases KRunner's Shell runner would also react to."""
    return sorted(a for a in cmds if a[0].isalnum() and shutil.which(a))


# ── D-Bus service ────────────────────────────────────────────────────────────

FOCUS_JS = r"""
(function () {
    var want = %s;             // exact resourceClass/resourceName matches
    var list = workspace.stackingOrder || [];
    var seen = [], best = null;
    for (var i = 0; i < list.length; i++) {   // bottom → top; keep the topmost match
        var w = list[i];
        if (!w) continue;
        var c = String(w.resourceClass).toLowerCase(), n = String(w.resourceName).toLowerCase();
        var cap = String(w.caption);
        if (c.indexOf("logos") >= 0 || n.indexOf("logos") >= 0 || c.indexOf(".exe") >= 0 ||
            cap.toLowerCase().indexOf("logos") >= 0 || want.indexOf(c) >= 0)
            seen.push({cls: c, name: n, caption: cap, normal: !!w.normalWindow,
                       skipTaskbar: !!w.skipTaskbar, minimized: !!w.minimized,
                       w: Math.round(w.width), h: Math.round(w.height)});
        // Wine creates invisible 1×1 helper windows that KWin also calls "normal";
        // only real, visible-sized windows count.
        if (!w.normalWindow || w.skipTaskbar || w.width < 100 || w.height < 100) continue;
        if (want.indexOf(c) >= 0 || want.indexOf(n) >= 0) best = w;
    }
    if (best) {
        if (best.minimized) best.minimized = false;
        if (typeof workspace.raiseWindow === "function") workspace.raiseWindow(best);
        if ("activeWindow" in workspace) workspace.activeWindow = best;
        else workspace.activeClient = best;
        var now = workspace.activeWindow || workspace.activeClient;
        seen.push({chosen: String(best.caption), activeAfter: now ? String(now.caption) : "(none)",
                   onDesktop: best.onCurrentDesktop !== false, activity: best.onAllActivities ? "all" : "this"});
    }
    callDBus("%s", "%s", "%s", "FocusResult", best !== null, JSON.stringify(seen));
})();
"""


def main_service():
    import dbus
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio, GLib

    def props(**kw):
        return dbus.Dictionary(kw, signature="sv")

    def icon_props(p, img):
        if img:
            w, h, rs, alpha, bps, ch, data = img
            p["icon-data"] = dbus.Struct(
                (dbus.Int32(w), dbus.Int32(h), dbus.Int32(rs), dbus.Boolean(alpha),
                 dbus.Int32(bps), dbus.Int32(ch), dbus.ByteArray(data)),
                signature="iiibiiay", variant_level=1)
        return p

    NO_ACTIONS = dbus.Array([], signature="s")

    class Runner(dbus.service.Object):
        def __init__(self, bus):
            self.bus_name = dbus.service.BusName(BUS_NAME, bus)
            super().__init__(self.bus_name, OBJ_PATH)
            self.bus = bus
            self.cfg = Config()
            self.lib = Library()
            self.cmds = {}
            self.token = ""
            self.focus_deadline = 0
            self.focus_script = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "logos-plasma-focus.js"
            self.focus_done = True
            self.focus_timers = []
            self.setup_notifications()
            self.refresh()

        def refresh(self):
            old = (self.cfg.mtime, self.lib._stamp)
            self.cfg.maybe_reload()
            self.lib.refresh(self.cfg.settings["logos_data"])
            if (self.cfg.mtime, self.lib._stamp) != old or not self.cmds:
                self.cmds = build_commands(self.cfg, self.lib)
                bad = conflicts(self.cmds)
                if bad:
                    log("aliases that are also programs on $PATH (Shell runner will match too):",
                        " ".join(bad))

        # krunner1 interface ---------------------------------------------------
        @dbus.service.method(IFACE, out_signature="a{sv}")
        def Config(self):
            return dbus.Dictionary({
                "MatchRegex": r"^\s*(?:['.]\S|\S+\s+\S|(?:%s)\s*$)" % "|".join(
                    re.escape(a) for a in (self.cfg.aliases.get(k) for k in ("help", "plans", "recent", "devotional")) if a),
                "MinLetterCount": dbus.Int32(2),
            }, signature="sv")

        @dbus.service.method(IFACE, out_signature="a(sss)")
        def Actions(self):
            return [("copy", "Copy Logos URL", "edit-copy")]

        @dbus.service.method(IFACE, in_signature="s")
        def SetActivationToken(self, token):
            self.token = token

        @dbus.service.method(IFACE)
        def Teardown(self):
            pass

        @dbus.service.method(IFACE, in_signature="s", out_signature="a(sssida{sv})")
        def Match(self, query):
            try:
                self.refresh()
                return self.match(query)
            except Exception as e:
                log(f"Match({query!r}) failed: {e!r}")
                return []

        @dbus.service.method(IFACE, in_signature="ss")
        def Run(self, match_id, action_id):
            if not match_id:
                return
            if action_id == "copy":
                if not set_clipboard(match_id, self.bus):
                    log("clipboard: couldn't set it")
                return
            self.launch(match_id)

        @dbus.service.method(INTERNAL_IFACE)
        def Focus(self):
            self.focus_deadline = time.monotonic() + 5
            self.focus_done = False
            self.focus_timers = [GLib.idle_add(self.focus)]

        @dbus.service.method(INTERNAL_IFACE)
        def FocusResult(self, found, info=""):
            log(f"focus: {'raised Logos' if found else 'no Logos window matched'}; candidates: {info}")
            if not found and time.monotonic() < self.focus_deadline:
                GLib.timeout_add(2000, self.focus)  # Logos is probably still starting

        # matching -------------------------------------------------------------
        def match(self, query):
            cmd, arg = split_query(query, self.cmds)
            if cmd is None:
                return self.bare_reference_rows(query)
            s = self.cfg.settings
            safe = s["safe_chars"]
            picker = lambda: self.lib.picker(s["picker_bibles"], s["picker_order"], s["picker_size"])

            if cmd.kind == "help":
                return self.help_rows(arg)
            if cmd.kind == "plans":
                return self.plan_rows(arg)
            if cmd.kind == "recent":
                return self.recent_rows(arg)
            if cmd.kind == "layout":
                return self.layout_rows(arg)
            if cmd.kind == "copy" and arg:
                return self.copy_rows(arg)
            if cmd.kind == "devotional":
                return self.devotional_rows(arg)
            if not arg:
                return [("", f"{cmd.name}: type {cmd.hint}", "logos-plasma", LOW, 0.5,
                         props(subtext=f"{cmd.alias} <{cmd.hint}>", actions=NO_ACTIONS))]

            if cmd.kind == "wordstudy":
                url = s["wordstudy_url"].replace("{q}", encode(arg, ""))
                return [(url, f"Bible Word Study: {arg}", "logos-plasma", HIGHEST, 1.0,
                         props(subtext=url))]

            if cmd.kind == "factbook":
                rows = []
                for i, f in enumerate(self.lib.factbook(arg)):
                    url = s["factbook_url"].replace("{key}", encode(f["key"], ""))
                    sub = f["description"] or f["kind"]
                    if f["alias"]:
                        sub = f"also “{f['alias']}” · {sub}"
                    rows.append((url, f["label"], FACTBOOK_ICONS.get(f["kind"], "help-about"),
                                 HIGHEST, 1.0 - i * 0.01, props(subtext=sub)))
                return rows or [("", f"Factbook: nothing found for “{arg}”", "help-about", LOW, 0.5,
                                 props(actions=NO_ACTIONS))]

            if cmd.kind == "url":
                q = encode(arg, cmd.extra.get("safe_chars", safe)) if cmd.extra.get("encode", True) else arg
                url = cmd.url.replace("{q}", q)
                return [(url, f"{cmd.name}: {arg}", cmd.extra.get("icon", "logos-plasma"),
                         HIGHEST, 1.0, props(subtext=url))]

            if cmd.kind == "library":
                rows = []
                for i, r in enumerate(self.lib.search_titles(arg.split())):
                    url = f"logosres:{r.logosres}"
                    p = props(subtext=r.abbr or r.resource_id)
                    if s["covers"]:
                        icon_props(p, self.lib.cover(r.record_id))
                    rows.append((url, r.title, "logos-plasma", HIGHEST, 1.0 - i * 0.01, p))
                return rows

            if cmd.kind == "top":
                url = (s["search_url"].replace("{q}", encode(arg, safe))
                       .replace("{scope}", s["top_bibles_scope"]))
                return [(url, f"Search Top Bibles: {arg}", "logos-plasma", HIGHEST, 1.0,
                         props(subtext="Logos's Top Bibles"))]

            if cmd.kind == "everything":
                url = s["library_search_url"].replace("{q}", encode(arg, safe))
                return [(url, f"Search your library: {arg}", "logos-plasma", HIGHEST, 1.0,
                         props(subtext="All your books"))]

            if cmd.kind in ("lexicon", "headword"):
                lexes = [cmd.bible] if cmd.bible else self.lib.lexicon_picker(arg, s["picker_size"])
                rows = []
                for i, l in enumerate(lexes):
                    url = (s["headword_url"].replace("{logosres}", l.logosres)
                           .replace("{q}", encode(arg, safe)))
                    p = props(subtext=l.title)
                    if s["covers"]:
                        icon_props(p, self.lib.cover(l.record_id))
                    rows.append((url, f"{l.abbr or l.title}: {arg}", "logos-plasma",
                                 HIGHEST, 1.0 - i * 0.01, p))
                return rows

            if cmd.kind == "compare":
                res = ",".join(b.logosres for b in picker())
                url = s["compare_url"].replace("{q}", encode(arg, safe)).replace("{resources}", res)
                return [(url, f"Text Comparison: {arg}", "logos-plasma", HIGHEST, 1.0,
                         props(subtext=", ".join(b.abbr for b in picker())))]

            # open / search / phrase / words: one Bible, or a picker of top Bibles
            bibles = [cmd.bible] if cmd.bible else None
            if bibles is None:
                first, _, rest = arg.partition(" ")
                if rest and norm(first) in self.lib.by_key:  # `o esv John 1`
                    bibles, arg = [self.lib.by_key[norm(first)]], rest.strip()
                else:
                    bibles = picker()
            if not bibles:
                return [("", f"{cmd.name}: no Bibles found", "dialog-warning", LOW, 0.5,
                         props(subtext=self.lib.error or "check picker_bibles in commands.toml",
                               actions=NO_ACTIONS))]
            tmpl = {"open": s["open_url"], "search": s["search_url"], "words": s["search_url"],
                    "phrase": s["phrase_url"]}[cmd.kind]
            label = {"open": "{abbr}: {arg}", "search": "Search {abbr}: {arg}",
                     "words": "Search {abbr}: {arg}", "phrase": "Search {abbr}: “{arg}”"}[cmd.kind]
            rows = []
            if (cmd.kind != "open" and cmd.bible is None and len(bibles) > 1
                    and s["search_top_row"]):
                url = tmpl.replace("{q}", encode(arg, safe)).replace("{scope}", s["top_bibles_scope"])
                rows.append((url, label.format(abbr="Top Bibles", arg=arg), "logos-plasma",
                             HIGHEST, 1.0, props(subtext="Logos's Top Bibles")))
            for i, b in enumerate(bibles, start=len(rows)):
                url = (tmpl.replace("{q}", encode(arg, safe))
                       .replace("{scope}", f"Single|ResourceId={b.resource_id}")
                       .replace("{res}", b.resource_id)
                       .replace("{logosres}", b.logosres))
                p = props(subtext=b.title)
                if s["covers"]:
                    icon_props(p, self.lib.cover(b.record_id))
                rows.append((url, label.format(abbr=b.abbr, arg=arg), "logos-plasma",
                             HIGHEST, 1.0 - i * 0.01, p))
            return rows

        def bare_reference_rows(self, query):
            s = self.cfg.settings
            if not s["bare_references"]:
                return []
            q = query.strip()
            refs = find_references(q)
            # only when the query is essentially just references, not a sentence
            if not refs or len(re.sub(r"[\W\d_]", "", q)) > len(" ".join(refs)) + 4:
                return []
            rows = []
            for i, ref in enumerate(refs[:5]):
                url = s["reference_url"].replace("{q}", encode(ref, ":,."))
                rows.append((url, f"Open {ref} in Logos", "logos-plasma", HIGHEST, 0.9 - i * 0.01,
                             props(subtext="Your preferred Bible" if url.startswith("logosref:") else url)))
            return rows

        def recent_rows(self, flt):
            rows = []
            items = self.lib.recent(self.cfg.settings["open_url"], limit=30)
            items = [r for r in items if flt.lower() in (r["title"] + r["subtitle"]).lower()][:10]
            for i, r in enumerate(items):
                p = props(subtext=r["subtitle"] or "Recently opened")
                if self.cfg.settings["covers"]:
                    icon_props(p, self.lib.cover_for(r["resourceId"]))
                rows.append((r["url"], r["title"], "document-open-recent", HIGHEST, 1.0 - i * 0.01, p))
            return rows

        def copy_rows(self, text):
            refs = find_references(text, loose=True)
            if not refs:
                return [("", "Copy verses: type a passage", "edit-copy", LOW, 0.5,
                         props(subtext="e.g. cv John 3:16-18", actions=NO_ACTIONS))]
            return [(COPY_PREFIX + r, f"Copy {r}", "edit-copy", HIGHEST, 1.0 - i * 0.01,
                     props(subtext="As text: your preferred Bible, in your Copy Bible Verses style",
                           actions=NO_ACTIONS))
                    for i, r in enumerate(refs[:5])]

        def layout_rows(self, flt):
            # "lay passage john 3:16": the reference is cut out; the other words filter layouts
            ref, flt = split_reference(flt)
            words = flt.lower().split()
            names = [n for n in self.lib.layouts() if all(w in n.lower() for w in words)]
            if not names:
                return [("", "No saved layout matches" if flt else "No saved layouts",
                         "view-split-left-right", LOW, 0.5,
                         props(subtext="Save one in Logos: Layouts → Save as named layout", actions=NO_ACTIONS))]
            suffix = f"::{ref}" if ref else ""
            return [(LAYOUT_PREFIX + n + suffix, f"{n}: {ref}" if ref else n, "view-split-left-right",
                     HIGHEST, 1.0 - i * 0.001,
                     props(subtext=f"Open this layout at {ref}" if ref else "Logos layout", actions=NO_ACTIONS))
                    for i, n in enumerate(names[:20])]

        def devotional_rows(self, flt):
            s = self.cfg.settings
            devs = self.lib.devotionals(s["devotionals"]) if not flt else [
                d for d in self.lib.devotionals() if flt.lower() in (d.title + " " + d.abbr).lower()]
            featured = {d.resource_id for d in self.lib.default_devotionals(s["devotionals"])}
            if not flt:
                devs = sorted(devs, key=lambda d: d.resource_id not in featured)
            rows = []
            for i, d in enumerate(devs[:8]):
                url = s["devotional_url"].replace("{logosres}", d.logosres)
                p = props(subtext="Today's reading" + (" · prioritized" if d.rank else ""))
                if s["covers"]:
                    icon_props(p, self.lib.cover(d.record_id))
                rows.append((url, d.title, "view-calendar-day", HIGHEST, 1.0 - i * 0.01, p))
            return rows

        # Reminders ------------------------------------------------------------
        def setup_notifications(self):
            self.notif_actions = {}
            self.bus.add_signal_receiver(self.on_notification_action, "ActionInvoked",
                                         "org.freedesktop.Notifications")
            self.bus.add_signal_receiver(self.on_notification_closed, "NotificationClosed",
                                         "org.freedesktop.Notifications")

        def on_notification_action(self, nid, action):
            url = self.notif_actions.pop(int(nid), {}).get(str(action))
            if url:
                self.launch(url)
                try:
                    self.bus.get_object("org.freedesktop.Notifications", "/org/freedesktop/Notifications",
                                        introspect=False).CloseNotification(
                        dbus.UInt32(nid), dbus_interface="org.freedesktop.Notifications")
                except dbus.DBusException:
                    pass

        def on_notification_closed(self, nid, reason):
            self.notif_actions.pop(int(nid), None)

        @dbus.service.method(INTERNAL_IFACE)
        def CheckReminders(self):
            try:
                self.check_reminders()
            except Exception as e:
                log(f"reminders: {e!r}")

        def check_reminders(self):
            import datetime as dt
            s = self.cfg.settings
            self.refresh()
            state_path = Path(os.environ.get("XDG_STATE_HOME", HOME / ".local/state")) / "logos-plasma" / "reminders.json"
            try:
                state = json.loads(state_path.read_text())
            except (OSError, ValueError):
                state = {}
            now = dt.datetime.now()
            today = now.date().isoformat()
            due = []
            if s["reminders"]:
                for plan in self.lib.reading_plans(s["open_url"]):
                    t = plan.get("notificationTime")
                    if (plan["kind"] != "today" or not t or plan["behind"] is None
                            or plan["behind"] < 0 or state.get(plan["title"]) == today):
                        continue
                    if now.strftime("%H:%M") >= t:
                        due.append((plan["title"], plan["summary"] + (f" · {plan['dueLabel']}" if plan["dueLabel"] else ""),
                                    plan["readings"][0]["url"] if plan["readings"] else ""))
            dtime = s["devotional_reminder"]
            if dtime and now.strftime("%H:%M") >= dtime and state.get("__devotional__") != today:
                for d in self.lib.default_devotionals(s["devotionals"])[:1]:
                    due.append(("__devotional__", d.title, s["devotional_url"].replace("{logosres}", d.logosres)))
            for title, body, url in due:
                summary = "Today's devotional" if title == "__devotional__" else title
                nid = notify(summary, body, icon="view-calendar-day",
                             actions=["default", "Read now"] if url else [], bus=self.bus)
                if nid:
                    self.notif_actions[nid] = {"default": url}
                    state[title] = today
            if due:
                state_path.parent.mkdir(parents=True, exist_ok=True)
                state_path.write_text(json.dumps(state))

        def plan_rows(self, flt):
            rows = []
            plans = self.lib.reading_plans(self.cfg.settings["open_url"])
            plans = [p for p in plans if flt.lower() in p["title"].lower()][:5]
            for pi, plan in enumerate(plans):
                for ri, r in enumerate(plan["readings"][:6]):
                    p = props(subtext=f"{plan['title']} · {plan_status(plan)}")
                    if self.cfg.settings["covers"] and r.get("resourceId"):
                        icon_props(p, self.lib.cover_for(r["resourceId"]))
                    rows.append((r["url"], r["label"], "view-calendar-day", HIGHEST,
                                 1.0 - pi * 0.05 - ri * 0.005, p))
            if not rows:
                rows.append(("", "No active reading plans", "view-calendar-day", LOW, 0.5,
                             props(subtext=self.lib.error or "", actions=NO_ACTIONS)))
            return rows

        def help_rows(self, flt):
            """`logos`: a few grouped rows that fit KRunner's list; `logos <word>`: matching
            individual commands."""
            flt = flt.lower().strip()
            a = {k: v for k, v in self.cfg.aliases.items() if v}
            if not flt:
                eg = (self.lib.bibles[0].key if self.lib.bibles else "esv")
                groups = [
                    ("Open a passage", f"{a.get('open','o')} John 3:16 · {a.get('open','o')}{eg} John 3:16 · "
                                       "or just type John 3:16", "document-open"),
                    ("Search", f"{a.get('search','s')} grace · {a.get('top','stb')} grace (Top Bibles) · "
                               f"{a.get('everything','sll')} grace (library) · {a.get('phrase', chr(39))}phrase · "
                               f"{a.get('words','.')}any words", "search"),
                    ("Words & lexicons", f"{a.get('lexicon','lex')} ἀγάπη · o<lexicon> ἀγάπη (obdag) · "
                                         f"{a.get('wordstudy','ws')} agape", "accessories-dictionary"),
                    ("Factbook, books & guides", f"{a.get('factbook','fb')} moses · {a.get('library','ol')} bavinck · "
                                                f"{a.get('recent','or')} (recent) · {a.get('compare','otc')} Ruth 1 · "
                                                + " · ".join(c.alias for c in self.cmds.values() if c.kind == "url")[:60],
                     "view-list-details"),
                    ("Every day", f"{a.get('plans','rp')} (reading plans) · {a.get('devotional','today')} (devotional) · "
                                  f"{a.get('layout','lay')} (your layouts) · {a.get('copy','cv')} (copy verses) · "
                                  "Alt+Shift+L looks up a copied reference", "view-calendar-day"),
                    (f"{a.get('help','logos')} <word> lists matching commands", "e.g. logos search · logos fb", "help-about"),
                ]
                # Moderate, so typing "logos" + Enter still launches the Logos app first.
                return [("", title, icon, MODERATE, 0.9 - i * 0.01, props(subtext=sub, actions=NO_ACTIONS))
                        for i, (title, sub, icon) in enumerate(groups)]
            rows, seen = [], set()
            for alias, c in sorted(self.cmds.items()):
                text = f"{alias}  —  {c.name}"
                if (c.bible is not None and flt not in alias) or flt not in (text + " " + c.kind).lower():
                    continue
                if text in seen:
                    continue
                seen.add(text)
                rows.append(("", text, "logos-plasma", HIGHEST, 0.8 - len(rows) * 0.001,
                             props(subtext=f"{alias} <{c.hint}>", actions=NO_ACTIONS)))
            for text, sub in [("John 3:16  —  any Bible reference", "Opens in your preferred Bible"),
                              ("Alt+Shift+L  —  Look up in Logos", "Opens the reference (or word) in the clipboard")]:
                if flt in text.lower():
                    rows.append(("", text, "logos-plasma", HIGHEST, 0.7, props(subtext=sub, actions=NO_ACTIONS)))
            return rows[:20]

        # launching ------------------------------------------------------------
        def launch(self, url):
            s = self.cfg.settings
            if url.startswith(COPY_PREFIX):
                ref = url[len(COPY_PREFIX):]
                log(f"copying {ref}")
                copy_verses(ref, lambda result: self.copy_done(ref, result))
                return
            if url.startswith(LAYOUT_PREFIX):
                name, _, ref = url[len(LAYOUT_PREFIX):].partition("::")
                log(f"loading layout {name!r}" + (f" at {ref}" if ref else ""))
                load_layout(name, lambda result: self.layout_done(name, result), ref=ref)
                if s["focus"]:
                    self.stop_focusing()
                    self.focus_done = False
                    self.focus_timers = [GLib.timeout_add(int(ms), self.focus)
                                         for ms in s.get("focus_attempts_ms", (350, 1200, 2500, 4000, 6000, 9000))]
                return
            if not s["link_cloud_books"]:
                try:
                    self.refresh()
                    info = self.lib.resource_for_link(url)
                except Exception as e:
                    info = None
                    log(f"availability check failed: {e}")
                if info and info[1] == 1:
                    title = info[0]
                    log(f"not opening cloud-only book by link (crashes Logos under Wine): {title}")
                    set_clipboard(title, self.bus)
                    notify("Download this book in Logos first",
                           f"“{title}” isn't downloaded yet, and opening it by link can crash Logos. "
                           "Its title is on the clipboard: paste it into Logos's Library to download it.",
                           bus=self.bus)
                    self.focus_deadline = time.monotonic() + 5
                    self.focus_done = False
                    self.focus_timers = [GLib.timeout_add(200, self.focus)]
                    return
            token, self.token = self.token, ""
            log(f"launching {url}")
            launch_with_handler(url, s["handler"], token)
            if s["focus"]:
                self.focus_deadline = time.monotonic() + 90
                # Ou Dedetai starts a second Logos process to hand the link to the running
                # one, which can take several seconds; keep raising Logos until then.
                self.stop_focusing()
                self.focus_done = False
                self.focus_timers = [GLib.timeout_add(int(ms), self.focus)
                                     for ms in s.get("focus_attempts_ms", (350, 1200, 2500, 4000, 6000, 9000))]

        def focus(self):
            """One raise attempt, in a separate short-lived process (as --focus-test, which
            works where in-service KWin calls didn't). Stops all further attempts once Logos
            is confirmed as the active window."""
            if self.focus_done:
                return False
            if desktop() != "kde":
                # Raising another app's window needs KWin scripting. Elsewhere (GNOME) the
                # desktop shows its own "Logos is ready" notification instead, which is normal there.
                self.focus_done = True
                return False
            try:
                proc = Gio.Subprocess.new([sys.executable, os.path.abspath(__file__), "--raise"],
                                          Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE)
                proc.communicate_utf8_async(None, None, self.on_raised)
            except Exception as e:
                log(f"focus: couldn't start raise helper: {e}")
            return False  # one-shot GLib timeout

        def on_raised(self, proc, res):
            try:
                _, out, _ = proc.communicate_utf8_finish(res)
                r = json.loads((out or "").strip().splitlines()[-1])
            except Exception as e:
                log(f"focus: raise helper failed: {e}")
                return
            ok = r.get("found") and r.get("chosen") and r.get("activeAfter") == r.get("chosen")
            log(f"focus: {'Logos is in front' if ok else 'not yet'} "
                f"(chose “{r.get('chosen')}”, active “{r.get('activeAfter')}”)")
            if ok:
                self.stop_focusing()
            elif not r.get("found") and time.monotonic() < self.focus_deadline:
                self.focus_timers.append(GLib.timeout_add(2000, self.focus))  # Logos still starting

        def copy_done(self, ref, result):
            ok, text = result
            if not ok:
                notify("Couldn't copy the verses", f"{ref}: {text}", bus=self.bus)
                return
            if not set_clipboard(text, self.bus):
                notify("Couldn't copy the verses", "Couldn't reach the clipboard (install wl-clipboard).", bus=self.bus)
                return
            preview = " ".join(text.split())
            notify(f"Copied {ref}", preview[:140] + ("…" if len(preview) > 140 else ""), bus=self.bus)

        def layout_done(self, name, result):
            log(f"layout {name!r}: {result}")
            if result == "missing":
                notify("No such Logos layout", f"There's no saved layout called “{name}”.", bus=self.bus)
            elif result != "loaded":
                notify("Couldn't open the layout", f"{name}: {result}\n"
                       "Try: python3 ~/.local/share/logos-plasma/logos_plasma.py --register-com", bus=self.bus)

        def stop_focusing(self):
            self.focus_done = True
            ctx = GLib.MainContext.default()
            for t in self.focus_timers:
                src = ctx.find_source_by_id(t)
                if src is not None and not src.is_destroyed():
                    src.destroy()
            self.focus_timers = []

    class SearchProvider(dbus.service.Object):
        """GNOME Shell's search interface (the Activities overview), answering from the same
        commands as KRunner. GNOME asks for result ids, then for each id's name, description
        and icon, and activates an id when it's clicked."""

        def __init__(self, runner):
            super().__init__(runner.bus_name, SEARCH_PATH)
            self.runner = runner
            self.rows = {}  # result id → KRunner-style row from the last searches

        def search(self, terms):
            query = " ".join(terms)
            try:
                self.runner.refresh()
                rows = self.runner.match(query)
            except Exception as e:
                log(f"search({query!r}) failed: {e!r}")
                return []
            rows = sorted(rows, key=lambda r: -float(r[4]))
            if len(self.rows) > 500:
                self.rows.clear()
            ids = []
            for i, row in enumerate(rows):
                rid = f"{i}\x1f{row[0] or row[1]}"  # unique even for rows with no link (help rows)
                self.rows[rid] = row
                ids.append(rid)
            return dbus.Array(ids, signature="s")

        @dbus.service.method(SEARCH_IFACE, in_signature="as", out_signature="as")
        def GetInitialResultSet(self, terms):
            return self.search(terms)

        @dbus.service.method(SEARCH_IFACE, in_signature="asas", out_signature="as")
        def GetSubsearchResultSet(self, previous, terms):
            return self.search(terms)

        @dbus.service.method(SEARCH_IFACE, in_signature="as", out_signature="aa{sv}")
        def GetResultMetas(self, ids):
            metas = []
            for rid in ids:
                row = self.rows.get(rid)
                if row is None:
                    continue
                link, text, icon, _cat, _rel, props = row
                meta = {"id": rid, "name": text, "description": str(props.get("subtext", ""))}
                if "icon-data" in props:
                    meta["icon-data"] = props["icon-data"]
                else:
                    meta["gicon"] = icon or "logos-plasma"
                metas.append(dbus.Dictionary(meta, signature="sv"))
            return dbus.Array(metas, signature="a{sv}")

        @dbus.service.method(SEARCH_IFACE, in_signature="sasu")
        def ActivateResult(self, rid, terms, timestamp):
            row = self.rows.get(rid)
            if row and row[0]:
                self.runner.launch(row[0])

        @dbus.service.method(SEARCH_IFACE, in_signature="asu")
        def LaunchSearch(self, terms, timestamp):
            # Clicking the provider's own icon: search Logos for the words
            alias = self.runner.cfg.aliases.get("search") or "s"
            rows = [r for r in self.runner.match(f"{alias} {' '.join(terms)}") if r[0]]
            if rows:
                self.runner.launch(rows[0][0])

    DBusGMainLoop(set_as_default=True)
    runner = Runner(dbus.SessionBus())
    SearchProvider(runner)
    GLib.MainLoop().run()


FACTBOOK_ICONS = {
    "Man": "im-user", "Woman": "im-user", "SupernaturalBeing": "starred-symbolic",
    "PeopleGroup": "system-users", "City": "mark-location", "OtherPlace": "mark-location",
    "NaturalPlace": "mark-location", "ManMadePlace": "mark-location", "Thing": "package",
    "ClassOfThing": "package", "Event": "view-calendar", "PreachingTheme": "view-media-lyrics",
    "Topic": "tag", "WordSense": "accessories-dictionary", "Culture": "applications-education",
}


def desktop():
    """'kde', 'gnome' or 'other', from the session's XDG_CURRENT_DESKTOP."""
    names = [d.strip().lower() for d in os.environ.get("XDG_CURRENT_DESKTOP", "").split(":")]
    if "kde" in names or os.environ.get("KDE_FULL_SESSION") == "true":
        return "kde"
    if "gnome" in names:
        return "gnome"
    return "other"


def set_clipboard(text, bus=None):
    """Put text on the clipboard: Klipper on Plasma, else wl-copy (Wayland) or xclip (X11)."""
    import subprocess
    if desktop() == "kde":
        try:
            import dbus
            (bus or dbus.SessionBus()).get_object("org.kde.klipper", "/klipper", introspect=False) \
                .setClipboardContents(text, dbus_interface="org.kde.klipper.klipper")
            return True
        except Exception:
            pass
    for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"]):
        if shutil.which(cmd[0]):
            try:
                subprocess.run(cmd, input=text, text=True, timeout=5, check=True)
                return True
            except (OSError, subprocess.SubprocessError):
                continue
    return False


def read_clipboard(selection=False):
    """Clipboard (or primary selection) text, via Klipper or wl-paste/xclip."""
    import subprocess
    cmds = ([["wl-paste", "--primary", "--type", "text", "--no-newline"], ["xclip", "-o", "-selection", "primary"]]
            if selection else [["wl-paste", "--type", "text", "--no-newline"], ["xclip", "-o", "-selection", "clipboard"]])
    if not selection and desktop() == "kde":
        try:
            import dbus
            text = dbus.SessionBus().get_object("org.kde.klipper", "/klipper").getClipboardContents(
                dbus_interface="org.kde.klipper.klipper")
            if text:
                return str(text)
        except Exception:
            pass
    for cmd in cmds:
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=3).stdout
        except (OSError, subprocess.SubprocessError):
            continue
    return ""


def logos_scan(text):
    """Bible references in text, found by Logos's own parser (it reads "jn 1v10", "John 1 10",
    ranges, lists…). Only while Logos is running, as it would otherwise have to start Logos
    just to parse. Returns [(query, display)] with query ready for reference_url's {q}
    ("Jn1.10"), or None when Logos isn't running or can't be asked."""
    if not find_oudedetai():
        return None
    try:
        SCAN_IN.parent.mkdir(parents=True, exist_ok=True)
        SCAN_IN.write_text(text, encoding="utf-16")
        SCAN_OUT.unlink(missing_ok=True)
    except OSError as e:
        log(f"scan: {e}")
        return None
    out = run_logos_script(SCAN_VBS, [], timeout=30)
    if not any(line.strip().startswith("found ") for line in out.splitlines()):
        log(f"scan: {script_result(out, ('notrunning',))}")  # not running, or Logos couldn't be asked
        return None
    try:
        out = SCAN_OUT.read_text(encoding="utf-16")
    except OSError:
        return None
    refs = []
    for line in out.splitlines():
        saved, _, display = line.strip().partition("\t")
        if saved:
            q = saved.split(".", 1)[1] if "." in saved else saved  # "Bible.Jn1.10" → "Jn1.10"
            refs.append((q, display or saved))
    return refs


def lookup_references(text):
    """[(query, display)]: ours first (instant), then Logos's parser for anything ours
    doesn't understand, if Logos is running (it costs a few seconds through Wine)."""
    if not text.strip():
        return []
    ours = find_references(text, loose=len(text.strip()) <= 40)
    if ours:
        return [(encode(r, ":,."), r) for r in ours]
    return logos_scan(text) or []


GNOME_PROVIDER_DIR = XDG_DATA / "logos-plasma" / "gnome-shell-data"  # added to XDG_DATA_DIRS
GNOME_KEYS = "org.gnome.settings-daemon.plugins.media-keys"
GNOME_SHORTCUT = "/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/logos-lookup/"
GNOME_DEFAULT_KEY = "<Shift><Alt>l"


def shortcut_key(desk=None):
    """The key bound to Look up in Logos: a string, "" if the entry has no key, None if absent."""
    import ast
    import subprocess
    desk = desk or desktop()
    if desk == "gnome":
        try:
            r = subprocess.run(["gsettings", "get", f"{GNOME_KEYS}.custom-keybinding:{GNOME_SHORTCUT}", "binding"],
                               capture_output=True, text=True, timeout=10)
            return ast.literal_eval(r.stdout.strip()) if r.returncode == 0 else None
        except (OSError, ValueError, SyntaxError, subprocess.SubprocessError):
            return None
    sc = XDG_CONFIG / "kglobalshortcutsrc"
    if not sc.exists():
        return None
    m = re.search(r"^\[services\]\[logos-plasma-lookup\.desktop\]\n(?:[^\[\n][^\n]*\n)*?_launch=([^\n]*)",
                  sc.read_text(errors="ignore"), re.M)
    return m.group(1).strip() if m else None


def gnome_shortcut(action="install"):
    """Add (or remove) the Look up in Logos custom shortcut on GNOME, as Settings → Keyboard →
    Custom Shortcuts would. Keeps a key you've set; won't take one that's already in use."""
    import ast
    import subprocess

    def gs(*args):
        r = subprocess.run(["gsettings", *args], capture_output=True, text=True, timeout=10)
        if r.returncode:
            raise RuntimeError(r.stderr.strip() or f"gsettings {' '.join(args)} failed")
        return r.stdout.strip()

    def paths():
        v = gs("get", GNOME_KEYS, "custom-keybindings")
        return ast.literal_eval(v[3:].strip() if v.startswith("@as") else v)

    one = f"{GNOME_KEYS}.custom-keybinding:{GNOME_SHORTCUT}"
    if not shutil.which("gsettings"):
        print("gsettings not found (is this GNOME?)")
        return 1
    current = paths()
    if action == "remove":
        if GNOME_SHORTCUT in current:
            gs("set", GNOME_KEYS, "custom-keybindings", str([p for p in current if p != GNOME_SHORTCUT]))
        for k in ("name", "command", "binding"):
            subprocess.run(["gsettings", "reset", one, k], capture_output=True)
        print("Removed the Look up in Logos shortcut")
        return 0
    if GNOME_SHORTCUT not in current:
        gs("set", GNOME_KEYS, "custom-keybindings", str(current + [GNOME_SHORTCUT]))
    def q(text):  # a GVariant string literal
        return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"

    def pretty(k):  # "<Shift><Alt>l" → "Alt+Shift+L"
        mods = [m.strip("<>").replace("Primary", "Ctrl").replace("Control", "Ctrl") for m in re.findall(r"<[^>]+>", k)]
        order = {"Ctrl": 0, "Super": 1, "Alt": 2, "Shift": 3}
        return "+".join(sorted(mods, key=lambda m: order.get(m, 9)) + [re.sub(r"<[^>]+>", "", k).upper()])

    gs("set", one, "name", q("Look up in Logos"))
    gs("set", one, "command", q(f"/usr/bin/python3 {Path(__file__).resolve()} --lookup"))
    key = ast.literal_eval(gs("get", one, "binding"))
    if key:
        print(f"Look up in Logos: kept your key {pretty(key)}")
        return 0
    def norm(k):
        return "".join(sorted(re.findall(r"<[^>]+>", k.lower()))) + re.sub(r"<[^>]+>", "", k.lower())
    want = norm(GNOME_DEFAULT_KEY)
    taken = [line.split(" ", 2)[:2] for line in gs("list-recursively").splitlines()
             if any(norm(k) == want for k in re.findall(r"'([^']*)'", line.split(" ", 2)[-1]))]
    if taken:
        print(f"Look up in Logos: {pretty(GNOME_DEFAULT_KEY)} is already used by {' '.join(taken[0])}; "
              "choose a key in Settings → Keyboard → Custom Shortcuts")
        return 0
    gs("set", one, "binding", q(GNOME_DEFAULT_KEY))
    print(f"Look up in Logos: {pretty(GNOME_DEFAULT_KEY)}")
    return 0


def cli_lookup(selection=False):
    """Global-shortcut action: open the Bible reference you've selected or copied in Logos
    (the selection first, then the clipboard); a single word goes to Bible Word Study."""
    cfg = Config()
    cfg.maybe_reload()
    s = cfg.settings
    sources = [read_clipboard(True).strip()]
    if not selection:
        clip = read_clipboard(False).strip()
        if clip and clip != sources[0]:
            sources.append(clip)
    for text in sources:
        refs = lookup_references(text)
        if refs:
            cli_open(s["reference_url"].replace("{q}", refs[0][0]))
            if len(refs) > 1:
                notify(f"Opened {refs[0][1]}", "Also there: " + ", ".join(d for _, d in refs[1:6]))
            return
    text = next((t for t in sources if t), "")
    words = text.split()
    if 0 < len(words) <= 2 and len(text) <= 40:
        cli_open(s["wordstudy_url"].replace("{q}", encode(text, "")))
        return
    notify("No Bible reference found",
           ("In: “" + text[:80] + ("…”" if len(text) > 80 else "”")) if text else "Nothing is selected or copied.")


def plan_status(plan):
    b = plan.get("behind")
    where = f"session {plan['session']} of {plan['total']}"
    if b is None:
        return where
    if b > 1:
        return f"{where} · {b} days behind"
    if b == 1:
        return f"{where} · yesterday's"
    if b == 0:
        return f"{where} · today"
    return f"{where} · due {plan['date']}"


def cli_reading_plans():
    cfg = Config()
    cfg.maybe_reload()
    lib = Library()
    lib.refresh(cfg.settings["logos_data"])
    plans = lib.reading_plans(cfg.settings["open_url"])
    for p in plans:
        p["status"] = plan_status(p)
    s = cfg.settings
    for d in lib.default_devotionals(s["devotionals"]):
        plans.insert(0, {
            "title": d.title, "kind": "devotional", "summary": "Today's reading", "dueLabel": "",
            "streak": 0, "minutes": None, "progress": 0, "behind": None, "session": 0, "total": 0,
            "status": "Devotional", "sessionTitle": "", "lastActivity": "", "coverResource": d.resource_id,
            "readings": [{"label": d.title, "short": None, "resourceId": d.resource_id,
                          "url": s["devotional_url"].replace("{logosres}", d.logosres)}]})
        try:
            p["cover"] = lib.cover_file(p["coverResource"])
        except Exception as e:
            log(f"cover: {e}")
            p["cover"] = ""
    print(json.dumps(plans, ensure_ascii=False))


LAYOUT_PREFIX = "layout:"  # our own scheme: layout:<name> opens a saved Logos layout


def find_oudedetai():
    """Ou Dedetai's launcher, which runs programs in Logos's Wine prefix (--wine)."""
    for p in sorted(glob.glob(str(XDG_DATA / "FaithLife-Community" / "*" / "oudedetai"))):
        if os.access(p, os.X_OK):
            return p
    return None


def wine_prefix(data_dir):
    """…/<prefix>/drive_c/users/<you>/AppData/Local/Logos/Data/<user> → <prefix>"""
    if not data_dir:
        return None
    for parent in Path(data_dir).parents:
        if parent.name == "drive_c":
            return parent.parent
    return None


def windows_path(path):
    return "Z:" + str(path).replace("/", "\\")


LAYOUT_VBS = XDG_DATA / "logos-plasma" / "loadlayout.vbs"
COPY_VBS = XDG_DATA / "logos-plasma" / "copyverses.vbs"
COPY_OUT = XDG_DATA / "logos-plasma" / "copyverses.txt"
SCAN_VBS = XDG_DATA / "logos-plasma" / "scanrefs.vbs"
SCAN_IN = XDG_DATA / "logos-plasma" / "scanrefs-in.txt"
SCAN_OUT = XDG_DATA / "logos-plasma" / "scanrefs-out.txt"
COPY_PREFIX = "copytext:"  # our own scheme: copytext:<reference> copies the passage as text


def run_logos_script(script, words, done=None, timeout=180):
    """Run one of our VBScripts with cscript inside the Logos Wine prefix (Ou Dedetai's
    --wine) and return its combined output; with done, run asynchronously and call
    done(output)."""
    o = find_oudedetai()
    if not o:
        out = "error: Ou Dedetai not found"
        return done(out) if done else out
    argv, env = logos_wine_command(o)
    argv += ["cscript", "//nologo", windows_path(script)] + list(words)
    if done is None:
        return subprocess_run(argv, timeout=timeout, env=env)
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio
    launcher = Gio.SubprocessLauncher.new(Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE)
    for k, v in (env or {}).items():
        launcher.setenv(k, v, True)
    proc = launcher.spawnv(argv)

    def finished(p, res):
        try:
            _, out, _ = p.communicate_utf8_finish(res)
        except Exception as e:
            out = f"error: {e}"
        done(out or "")
    proc.communicate_utf8_async(None, None, finished)


def script_result(out, answers):
    """The script's own result line ("loaded", "copied", "error: …") among Ou Dedetai's and
    Wine's log lines."""
    for line in (out or "").splitlines()[::-1]:
        line = line.strip()
        if line in answers or line.startswith("error:"):
            return line
    return "error: no answer from Logos (" + ((out or "").strip().splitlines() or ["nothing printed"])[-1][:100] + ")"


def copy_verses(ref, done=None):
    """Passage text from Logos's Copy Bible Verses (your preferred Bible and copy style).
    Returns (True, text) or (False, reason); with done, runs asynchronously."""
    def result(out):
        r = script_result(out, ("copied",))
        if r != "copied":
            return (False, r[len("error: "):] if r.startswith("error: ") else r)
        try:
            return (True, COPY_OUT.read_text(encoding="utf-16").strip())
        except OSError as e:
            return (False, str(e))
    try:
        COPY_OUT.unlink()
    except OSError:
        pass
    if done is None:
        return result(run_logos_script(COPY_VBS, ref.split(), timeout=60))
    run_logos_script(COPY_VBS, ref.split(), lambda out: done(result(out)), timeout=60)


def load_layout(name, done=None, ref=""):
    """Load a saved layout through Logos's COM API (LoadLayout), run with cscript inside
    the Logos Wine prefix, optionally sending its Bible to a passage. Calls done(result) with
    "loaded", "missing" or "error: …"; without done, waits and returns the result."""
    words = name.split() + (["::"] + ref.split() if ref else [])

    def result(out):
        for line in out.splitlines():
            if line.strip().startswith("passage:"):
                log(f"layout {line.strip()}")
        return script_result(out, ("loaded", "missing"))
    if done is None:
        return result(run_logos_script(LAYOUT_VBS, words))
    run_logos_script(LAYOUT_VBS, words, lambda out: done(result(out)))


def logos_wine_command(oudedetai):
    """How to run a Windows program in the Logos prefix: Ou Dedetai's own Wine, called
    directly (seconds faster than `oudedetai --wine`), else through Ou Dedetai.
    Returns (argv prefix, extra environment or None)."""
    wine = Path(oudedetai).parent / "data" / "bin" / "wine64"
    data, _ = find_logos_dirs()
    prefix = wine_prefix(data) if data else None
    if wine.exists() and prefix:
        return [str(wine)], {"WINEPREFIX": str(prefix), "WINEDEBUG": "-all"}
    return [oudedetai, "--wine"], None


def subprocess_run(argv, timeout=60, env=None):
    import subprocess
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, **env} if env else None)
        return r.stdout + r.stderr
    except Exception as e:
        return f"error: {e}"


def com_registered(prefix):
    try:
        return "[Software\\\\Classes\\\\LogosBibleSoftware.Launcher]" in \
            (Path(prefix) / "system.reg").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def register_com(data_dir, force=False):
    """Logos registers its COM API for the current user only, and Wine looks COM classes up
    machine-wide, so CreateObject fails. Copy Logos's own registration from the prefix's
    user.reg to HKLM\\Software\\Classes. Returns a short status string."""
    prefix = wine_prefix(data_dir) if data_dir else None
    if not prefix:
        return "Logos's Wine prefix not found"
    if com_registered(prefix) and not force:
        return "already registered"
    o = find_oudedetai()
    if not o:
        return "Ou Dedetai not found"
    text = (prefix / "user.reg").read_text(encoding="utf-8", errors="replace")
    sections = []
    for sec in re.split(r"\n(?=\[)", text):
        m = re.match(r"\[([^\]]+)\][^\n]*\n(.*)", sec, re.S)
        if m and m.group(1).startswith("Software\\\\Classes\\\\"):
            sections.append((m.group(1)[len("Software\\\\Classes\\\\"):], m.group(2)))
    guids = set()
    for name, body in sections:
        if "LogosCom.exe" in body or re.match(r"LogosBibleSoftware\.(Launcher|Application)", name):
            guids |= {g.upper() for g in re.findall(r"\{([0-9A-Fa-f-]{36})\}", name + body)}
    for name, body in sections:  # interfaces of the same type library
        if any(g in body.upper() for g in guids):
            guids |= {g.upper() for g in re.findall(r"\{([0-9A-Fa-f-]{36})\}", name)}
    guids.discard("00020424-0000-0000-C000-000000000046")  # oleaut's marshaller, already system-wide
    out = ["REGEDIT4", ""]
    for name, body in sections:
        if re.match(r"LogosBibleSoftware\.(Launcher|Application)", name) or any(g in name.upper() for g in guids):
            out.append("[HKEY_LOCAL_MACHINE\\Software\\Classes\\" + name.replace("\\\\", "\\") + "]")
            out += [l for l in body.splitlines() if re.match(r'^(@|"[^"]*")=("|dword:)', l)]
            out.append("")
    if len(out) < 6:
        return "Logos's COM registration not found in the prefix (is Logos installed?)"
    reg = XDG_DATA / "logos-plasma" / "logos-com-hklm.reg"
    reg.parent.mkdir(parents=True, exist_ok=True)
    reg.write_text("\r\n".join(out) + "\r\n")
    subprocess_run([o, "--wine", "regedit", "/S", windows_path(reg)], timeout=120)
    time.sleep(2)  # wineserver writes system.reg shortly after
    return "registered" if com_registered(prefix) else "registration didn't take (see logos-com-hklm.reg)"


def cli_open(url):
    """Open a Logos URL through the runner service (handler, no terminal, then focus).
    If the service can't be reached, run the handler's command line directly. Never use
    xdg-open: Ou Dedetai's handler has Terminal=true, which opens a terminal window."""
    import dbus
    try:
        dbus.SessionBus().get_object(BUS_NAME, OBJ_PATH).Run(url, "", dbus_interface=IFACE)
        return
    except dbus.DBusException as e:
        log(f"runner service unavailable ({e.get_dbus_name()}: {e}); launching the handler directly")
    if url.startswith(LAYOUT_PREFIX):
        name, _, ref = url[len(LAYOUT_PREFIX):].partition("::")
        log(f"layout: {load_layout(name, ref=ref)}")
        return
    cfg = Config()
    cfg.maybe_reload()
    launch_with_handler(url, cfg.settings["handler"])


def launch_with_handler(url, handler="", token=""):
    """Run the logos4: handler's command line with the URL, without a terminal."""
    gi.require_version("Gio", "2.0")
    from gi.repository import Gio
    info = Gio.DesktopAppInfo.new(handler) if handler else Gio.AppInfo.get_default_for_uri_scheme("logos4")
    if info is None:
        log("no logos4: handler registered (run Ou Dedetai's installer)")
        return False
    ctx = Gio.AppLaunchContext()
    if token:
        ctx.setenv("XDG_ACTIVATION_TOKEN", token)
    # Ou Dedetai's handler only declares logos4:/libronixdls: and sets Terminal=true;
    # reuse its command line so logosres:/logosref: links work and no terminal opens.
    Gio.AppInfo.create_from_commandline(
        info.get_commandline(), "Logos", Gio.AppInfoCreateFlags.SUPPORTS_URIS).launch_uris([url], ctx)
    return True


def kwin_run_script(bus, path, name):
    """Load and run a KWin script without blocking (Plasma 6 and 5 object paths)."""
    import dbus
    err = lambda e: log(f"KWin scripting error: {e}")
    scripting = dbus.Interface(bus.get_object("org.kde.KWin", "/Scripting", introspect=False),
                               "org.kde.kwin.Scripting")

    def run(sid):
        if sid < 0:
            log("KWin refused to load the focus script")
            return
        def try_path(paths):
            if not paths:  # last resort: start every loaded script
                scripting.start(reply_handler=lambda *a: None, error_handler=err)
                return
            bus.get_object("org.kde.KWin", paths[0], introspect=False).run(
                dbus_interface="org.kde.kwin.Script", reply_handler=lambda *a: None,
                error_handler=lambda e: try_path(paths[1:]))
        try_path([f"/Scripting/Script{sid}", f"/{sid}"])

    def load(*_):
        scripting.loadScript(str(path), name, reply_handler=run, error_handler=err)

    scripting.unloadScript(name, reply_handler=load, error_handler=load)


def raise_logos(timeout_ms=4000):
    """Ask KWin (via a one-off script) to raise the topmost real Logos window, in this
    process. Returns a dict: found, chosen, activeAfter, windows. Runs as its own short-lived
    process, which works reliably; the D-Bus-activated service delegates to it."""
    import dbus
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    tag = f"p{os.getpid()}"
    name = f"{BUS_NAME}.Raise.{tag}"
    loop = GLib.MainLoop()
    result = {"found": False, "chosen": "", "activeAfter": "", "windows": [], "replied": False}

    class Probe(dbus.service.Object):
        @dbus.service.method(INTERNAL_IFACE)
        def FocusResult(self, found, info=""):
            items = json.loads(info or "[]")
            chosen = next((w for w in items if "chosen" in w), {})
            result.update(found=bool(found), chosen=chosen.get("chosen", ""),
                          activeAfter=chosen.get("activeAfter", ""), replied=True,
                          onDesktop=chosen.get("onDesktop", True),
                          windows=[w for w in items if "chosen" not in w])
            loop.quit()

    Probe(dbus.service.BusName(name, bus), OBJ_PATH)
    cfg = Config()
    cfg.maybe_reload()
    plugin = f"logos-plasma-raise-{tag}"
    js_path = Path(os.environ.get("XDG_RUNTIME_DIR") or "/tmp") / f"{plugin}.js"
    js_path.write_text(FOCUS_JS % (json.dumps([c.lower() for c in cfg.settings["window_classes"]]),
                                   name, OBJ_PATH, INTERNAL_IFACE))
    kwin_run_script(bus, js_path, plugin)
    GLib.timeout_add(timeout_ms, loop.quit)
    loop.run()
    try:  # tidy up: unload our one-off script and its file
        dbus.Interface(bus.get_object("org.kde.KWin", "/Scripting", introspect=False),
                       "org.kde.kwin.Scripting").unloadScript(plugin)
    except Exception:
        pass
    js_path.unlink(missing_ok=True)
    return result


def focus_test():
    """Run the focus script once and print what KWin sees. Usage: --focus-test"""
    r = raise_logos(5000)
    if not r["replied"]:
        print("No reply from KWin within 5 s.")
        return
    print("Logos window raised:", r["found"], f"→ “{r['chosen']}”" if r["chosen"] else "")
    if r["chosen"]:
        print(f"  active window after: “{r['activeAfter']}”; on current desktop: {r['onDesktop']}")
    for w in r["windows"]:
        if w.get("normal") or "-v" in sys.argv:
            print(" ", w)
    if not r["windows"]:
        print("  (no window with 'logos' or '.exe' in its class, name or title)")


def check():
    cfg = Config()
    cfg.maybe_reload()
    lib = Library()
    lib.refresh(cfg.settings["logos_data"])
    print("config:   ", CONFIG_PATH, "(found)" if CONFIG_PATH.exists() else "(defaults)")
    print("catalog:  ", lib.catalog_path or lib.error)
    print("covers:   ", "yes" if GdkPixbuf else "no (install gir1.2-gdkpixbuf-2.0)")
    try:
        import gi as _gi
        _gi.require_version("Gio", "2.0")
        from gi.repository import Gio
        h = Gio.AppInfo.get_default_for_uri_scheme("logos4")
        print("handler:  ", h.get_id() if h else "NONE — run Ou Dedetai's installer")
    except Exception as e:
        print("handler:   ?", e)
    s = cfg.settings
    print(f"Bibles:    {len(lib.bibles)} owned")
    print("picker:   ", ", ".join(b.abbr for b in lib.picker(s["picker_bibles"], s["picker_order"], s["picker_size"])))
    cmds = build_commands(cfg, lib)
    print(f"commands:  {len(cmds)} ({sum(c.bible is None for c in cmds.values())} + per-Bible aliases)")
    bad = conflicts(cmds)
    print("conflicts:", " ".join(bad) if bad else "none")


SELFTEST_QUERIES = [  # (query, what a good first row looks like)
    ("logos", "help"), ("john 3:16", "url"), ("o john 3:16", "url"), ("oesv rom 8:28", "url"),
    ("s love", "url"), ("stb love", "url"), ("'faith hope love", "url"), (".grace peace", "url"),
    ("lex logos", "url"), ("ws agape", "url"), ("fb jesus", "url"), ("ol genesis", "url"),
    ("or", "url"), ("otc john 1:1", "url"), ("opg john 1", "url"), ("rp", "any"), ("today", "url"),
    ("lay", "layout"), ("cv john 3:16", "copy"),
]


def selftest():
    """Check everything that can be checked without clicking, and write the report to
    ~/.local/share/logos-plasma/selftest.txt (where it can be shared or read back)."""
    import subprocess
    lines, fails = [], []

    def out(ok, name, detail=""):
        mark = {True: "PASS", False: "FAIL", None: "skip"}[ok]
        lines.append(f"{mark}  {name}" + (f" — {detail}" if detail else ""))
        if ok is False:
            fails.append(name)

    version = XDG_DATA / "logos-plasma" / "VERSION"
    lines.append(f"Version {version.read_text().strip() if version.is_file() else 'unknown (before 0.5.1)'}")

    def attempt(name, fn):
        try:
            ok, detail = fn()
            out(ok, name, detail)
        except Exception as e:
            out(False, name, repr(e))

    cfg = Config()
    cfg.maybe_reload()
    lib = Library()
    lib.refresh(cfg.settings["logos_data"])
    s = cfg.settings
    desk = desktop()
    lines.append(f"logos-plasma self-test {time.strftime('%Y-%m-%d %H:%M')} · {platform_desc()}")
    lines.append("")
    lines.append("── Logos data (read-only) ──")
    out(bool(lib.catalog_path), "catalog found", str(lib.catalog_path or lib.error))
    if not lib.catalog_path:
        return finish(lines, fails)
    attempt("Bibles", lambda: (len(lib.bibles) > 0, f"{len(lib.bibles)} owned; picker: " + ", ".join(
        b.abbr for b in lib.picker(s["picker_bibles"], s["picker_order"], s["picker_size"]))))
    attempt("lexicons", lambda: (lambda l: (bool(l), ", ".join(x.abbr or x.title[:20] for x in l)))(
        lib.lexicon_picker("logos", s["picker_size"])))
    attempt("factbook “jesus”", lambda: (lambda f: (bool(f) and "jesus" in f[0]["label"].lower(),
            " · ".join(x["label"] for x in f[:3])))(lib.factbook("jesus")))
    attempt("recent books", lambda: (lambda r: (True, f"{len(r)}; latest: {r[0]['title'][:40]}" if r else "none"))(
        lib.recent(s["open_url"])))
    attempt("reading plans", lambda: (lambda p: (True, "; ".join(
        f"{x['title'][:30]} ({x['done']}/{x['total']}{', ' + x['dueLabel'] if x['dueLabel'] else ''})" for x in p[:4]) or "none"))(
        lib.reading_plans(s["open_url"])))
    attempt("devotionals", lambda: (lambda d: (True, ", ".join(x.title[:30] for x in d[:3]) or "none"))(
        lib.devotionals(s["devotionals"])))
    sermon = None
    try:
        sermon = lib.sermon_passage()
    except Exception as e:
        out(False, "sermon passage", repr(e))
    if sermon:
        out(True, "sermon passage", f"{sermon['title']} → {sermon['reference']} ({sermon['date'] or 'no date'})")
        attempt("sermon commentaries", lambda: (lambda c: (bool(c), f"{len(c)}: " + "; ".join(
            f"{x['myRating'] or x['rating']}★ {x['title'][:28]}" for x in c)))(
            lib.sermon_commentaries(sermon, int(s["showcase_sermon_commentaries"]))))
    else:
        out(None, "sermon passage", "no sermon document with a passage")
    attempt("saved layouts", lambda: (lambda l: (True, f"{len(l)}: " + ", ".join(l[:6]) + ("…" if len(l) > 6 else "")))(
        lib.layouts()))
    attempt("showcase shelf", lambda: (lambda b: (len(b) > 0, f"{len(b)} books, {sum(x['cloud'] for x in b)} not downloaded; "
            f"{sum(bool(x['cover']) for x in b)} with covers"))(lib.showcase(24)))

    lines.append("")
    lines.append(f"── Installation ({'KDE Plasma' if desk == 'kde' else 'GNOME' if desk == 'gnome' else desk}) ──")
    share = XDG_DATA
    files = [("lookup shortcut entry", share / "applications/logos-plasma-lookup.desktop"),
             ("reminders timer unit", XDG_CONFIG / "systemd/user/logos-plasma-reminders.timer")]
    if desk == "kde":
        files.insert(0, ("runner registered", share / "krunner/dbusplugins/logos-plasma.desktop"))
    if desk == "gnome":
        files += [("search provider", GNOME_PROVIDER_DIR / "gnome-shell/search-providers" / f"{BUS_NAME}.search-provider.ini"),
                  ("search provider folder added to your session",
                   XDG_CONFIG / "environment.d/60-logos-desktop-integrations.conf")]
    for name, path in files:
        out(path.exists(), name, str(path))
    if desk == "gnome":
        active = str(GNOME_PROVIDER_DIR) in os.environ.get("XDG_DATA_DIRS", "").split(":")
        out(active, "GNOME search can see it in this session", "" if active else "log out and back in once")
    try:
        h = subprocess.run(["xdg-mime", "query", "default", "x-scheme-handler/logos4"],
                           capture_output=True, text=True, timeout=5).stdout.strip()
        out(bool(h), "logos4: handler", h or "none — run Ou Dedetai's installer")
    except Exception as e:
        out(None, "logos4: handler", repr(e))
    try:
        r = subprocess.run(["systemctl", "--user", "is-active", "logos-plasma-reminders.timer"],
                           capture_output=True, text=True, timeout=5).stdout.strip()
        out(r == "active", "reminders timer running", r)
    except Exception as e:
        out(None, "reminders timer running", repr(e))
    if desk == "kde":
        try:
            r = subprocess.run(["kpackagetool6", "-t", "Plasma/Applet", "--list"],
                               capture_output=True, text=True, timeout=10).stdout
            for w in ("LogosVerseOfTheDay", "LogosReadingPlans", "LogosShowcase"):
                out(f"io.github.FaithlifeCommunity.{w}" in r, f"widget installed: {w}")
        except FileNotFoundError:
            out(None, "widgets installed", "kpackagetool6 not found")
    prefix = wine_prefix(lib.data_dir)
    out(bool(prefix) and com_registered(prefix), "Logos COM API registered (for layouts)",
        "run logos_plasma.py --register-com" if not (prefix and com_registered(prefix)) else str(prefix))
    key = shortcut_key(desk)
    out(bool(key), "Look up in Logos shortcut bound",
        key or ("no key: it may clash with another shortcut; set one in "
                + ("System Settings → Shortcuts" if desk == "kde" else "Settings → Keyboard → Custom Shortcuts")
                if key == "" else "not registered"))
    clip = shutil.which("wl-paste") or shutil.which("xclip")
    out(bool(clip), "reading highlighted text (wl-paste or xclip)",
        clip or "install wl-clipboard to look up highlighted text, not only copied text")

    lines.append("")
    try:
        import dbus
        bus = dbus.SessionBus()
        runner = bus.get_object(BUS_NAME, OBJ_PATH if desk != "gnome" else SEARCH_PATH)
    except Exception as e:
        out(None, "session bus", f"not reachable here ({e.__class__.__name__}); run this on your desktop")
        return finish(lines, fails)
    if desk == "gnome":
        lines.append("── Live GNOME search provider (over D-Bus, exactly what GNOME Shell sees) ──")
    else:
        lines.append("── Live KRunner plugin (over D-Bus, exactly what KRunner sees) ──")
    for q, want in SELFTEST_QUERIES:
        try:
            if desk == "gnome":
                ids = runner.GetInitialResultSet(q.split(), dbus_interface=SEARCH_IFACE, timeout=20)
                metas = runner.GetResultMetas(ids[:1], dbus_interface=SEARCH_IFACE, timeout=20) if ids else []
                rows = [(str(i).split("\x1f", 1)[-1], str(m.get("name", ""))) for i, m in zip(ids, metas)] \
                    + [("", "")] * max(0, len(ids) - len(metas))
            else:
                rows = runner.Match(q, dbus_interface=IFACE, timeout=20)
        except Exception as e:
            out(False, f"search “{q}”", repr(e)[:120])
            continue
        if not rows:
            out(False, f"search “{q}”", "no results")
            continue
        mid, title = str(rows[0][0]), str(rows[0][1])
        ok = want in ("help", "any") or mid.startswith(("logos4:", "logosres:", "logosref:", LAYOUT_PREFIX, COPY_PREFIX))
        out(ok, f"search “{q}”", f"{len(rows)} results; first: {title[:50]}" + (f" → {mid[:70]}" if mid else ""))
    try:
        info = bus.get_object("org.freedesktop.Notifications", "/org/freedesktop/Notifications") \
            .GetServerInformation(dbus_interface="org.freedesktop.Notifications")
        out(True, "notification server", f"{info[0]} {info[2]}")
    except Exception as e:
        out(False, "notification server", repr(e)[:100])
    if desk == "kde":
        try:
            bus.get_object("org.kde.KWin", "/Scripting", introspect=False)
            out(True, "KWin scripting (for bringing Logos to the front)")
        except Exception as e:
            out(False, "KWin scripting", repr(e)[:100])
    if "--live" in sys.argv:
        lines.append("")
        lines.append("── Live: opens John 3:16 in Logos and checks it comes to the front ──")
        cli_open(s["reference_url"].replace("{q}", "John3.16"))
        time.sleep(8)
        r = raise_logos()
        out(bool(r.get("found")) and r.get("chosen") == r.get("activeAfter"), "Logos is the active window",
            json.dumps({k: r.get(k) for k in ("found", "chosen", "activeAfter")}))
    return finish(lines, fails)


def platform_desc():
    import platform
    desk = os.environ.get("XDG_CURRENT_DESKTOP", "?")
    sess = os.environ.get("XDG_SESSION_TYPE", "?")
    return f"{desk} on {sess}, Python {platform.python_version()}"


def finish(lines, fails):
    lines.append("")
    lines.append(f"{'All checks passed' if not fails else str(len(fails)) + ' failed: ' + ', '.join(fails)}")
    text = "\n".join(lines) + "\n"
    print(text, end="")
    path = XDG_DATA / "logos-plasma" / "selftest.txt"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        print(f"(saved to {path})")
    except OSError:
        pass
    return 1 if fails else 0


if __name__ == "__main__":
    if "--gnome-shortcut" in sys.argv:
        i = sys.argv.index("--gnome-shortcut")
        sys.exit(gnome_shortcut(sys.argv[i + 1] if len(sys.argv) > i + 1 else "install"))
    elif "--register-com" in sys.argv:
        cfg = Config()
        cfg.maybe_reload()
        data, _ = find_logos_dirs(cfg.settings["logos_data"])
        print("Logos COM API:", register_com(data, force="--force" in sys.argv))
    elif "--copy-verses" in sys.argv:
        ref = " ".join(sys.argv[sys.argv.index("--copy-verses") + 1:])
        ok, text = copy_verses(ref)
        print(text if ok else f"error: {text}")
        sys.exit(0 if ok else 1)
    elif "--layouts" in sys.argv:
        cfg = Config()
        cfg.maybe_reload()
        lib = Library()
        lib.refresh(cfg.settings["logos_data"])
        print("\n".join(lib.layouts()))
    elif "--layout" in sys.argv:
        name, _, ref = " ".join(sys.argv[sys.argv.index("--layout") + 1:]).partition("::")
        print(load_layout(name.strip(), ref=ref.strip()))
    elif "--selftest" in sys.argv:
        sys.exit(selftest())
    elif "--check" in sys.argv:
        check()
    elif "--raise" in sys.argv:
        r = raise_logos()
        print(json.dumps({k: r[k] for k in ("found", "chosen", "activeAfter", "replied")}))
    elif "--focus-test" in sys.argv:
        focus_test()
    elif "--reading-plans" in sys.argv:
        cli_reading_plans()
    elif "--showcase" in sys.argv:
        cfg = Config()
        cfg.maybe_reload()
        lib = Library()
        lib.refresh(cfg.settings["logos_data"])
        i = sys.argv.index("--showcase")
        count = int(sys.argv[i + 1]) if len(sys.argv) > i + 1 and sys.argv[i + 1].isdigit() else 12
        seed = time.time() if "--shuffle" in sys.argv else None
        books = []
        if "--sermon" in sys.argv:  # the sermon shelf: your commentaries for the sermon passage
            n_sermon = int(cfg.settings.get("showcase_sermon_commentaries", 60))
            try:
                sermon = lib.sermon_passage()
                if sermon:
                    books = lib.sermon_commentaries(sermon, n_sermon)
            except Exception as e:
                log(f"sermon commentaries: {e!r}")
        if "--sermon" not in sys.argv or "--library" in sys.argv:  # well-rated, unread books
            books += lib.showcase(count, seed)
        print(json.dumps(books, ensure_ascii=False))
    elif "--lookup" in sys.argv:
        cli_lookup(selection="--selection" in sys.argv)
    elif "--check-reminders" in sys.argv:
        import dbus
        dbus.SessionBus().get_object(BUS_NAME, OBJ_PATH).CheckReminders(dbus_interface=INTERNAL_IFACE)
    elif "--focus" in sys.argv:
        import dbus
        dbus.SessionBus().get_object(BUS_NAME, OBJ_PATH).Focus(dbus_interface=INTERNAL_IFACE)
    elif "--open" in sys.argv:
        cli_open(sys.argv[sys.argv.index("--open") + 1])
    else:
        main_service()
