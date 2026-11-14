#!/usr/bin/python3
"""Logos Plasma integrations backend: KRunner D-Bus runner + helpers for the Plasma widgets.

Part of https://github.com/FaithLife-Community/logos-plasma-integrations (GPL-3.0-or-later).
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

HOME = Path.home()
XDG_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))
XDG_DATA = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share"))
CONFIG_PATH = XDG_CONFIG / "logos-plasma" / "commands.toml"

HIGHEST, LOW = 100, 30  # KRunner CategoryRelevance values

DEFAULTS = {
    "aliases": {
        "open": "o", "search": "s", "phrase": "'", "words": ".",
        "library": "ol", "compare": "otc", "help": "logos",
        "lexicon": "lex", "top": "stb", "everything": "sll", "plans": "rp",
        "wordstudy": "ws", "factbook": "fb", "recent": "or", "devotional": "today",
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
        "wordstudy_url": "logos4:Guide;t=My_Bible_Word_Study;hw={q}",
        "factbook_url": "logos4:Factbook;id=ref%3A{key};lens=all",
        # Opened by the "look up" shortcut and bare references in KRunner. logosref: uses the
        # preferred Bible set in Logos; use e.g. "logosres:esv;ref=Bible.{q}" for a fixed one.
        "reference_url": "logosref:Bible.{q}",
        "bare_references": True,     # typing just "John 3:16" in KRunner offers Logos
        "devotionals": [],           # titles/abbreviations; empty = your prioritized devotionals
        "devotional_url": "logosres:{logosres};ref=DayOfYear.today",
        "reminders": True,           # reading-plan notifications at each plan's reminder time
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


def find_references(text):
    """Bible references in free text → ['John 3:16', '1 Corinthians 13:4-7', …] (in order)."""
    out = []
    for m in _REF_RE.finditer(text or ""):
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
                if len(letters) <= 3 and not tail.lstrip("123 ")[:1].isupper():
                    continue
                num = BOOK_LOOKUP[key]
                break
        if num is None:
            continue
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
                            dbus.Dictionary({"desktop-entry": "logos-plasma-lookup"}, signature="sv"),
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
                    readings.append({"label": label, "short": short, "url": url, "resourceId": rid})
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
        path = self.data_dir / "AutoComplete" / "AutoComplete.db" if self.data_dir else None
        words = [w for w in re.findall(r"\w+", text.lower()) if w]
        if not path or not path.exists() or not words:
            return []
        first, rest = words[0], words[1:]
        with ro_connect(path) as c:
            rows = c.execute("""
                SELECT t.Reference, ik.IconKind, l.LabelText, l.IsPrimary,
                       (SELECT Description FROM Descriptions d WHERE d.TermId = t.TermId AND d.LanguageId = 1),
                       (SELECT LabelText FROM Labels p WHERE p.TermId = t.TermId AND p.IsPrimary = 1 AND p.LanguageId = 1)
                FROM LabelWords w JOIN Labels l ON l.LabelId = w.LabelId JOIN Terms t ON t.TermId = l.TermId
                LEFT JOIN IconKinds ik ON ik.IconKindId = t.IconKindId
                WHERE w.LanguageId = 1 AND w.FoldedText >= ? AND w.FoldedText < ?
                LIMIT 400""", (first, first + "\uffff")).fetchall()
        seen, out = set(), []
        for ref, kind, label, primary, desc, primary_label in rows:
            low = label.lower()
            if ref in seen or not all(w in low for w in rest):
                continue
            seen.add(ref)
            name = primary_label or label
            exact = name.lower() == text.lower().strip() or low == text.lower().strip()
            out.append({"key": ref, "kind": kind or "", "label": name,
                        "alias": "" if primary else label, "description": desc or "",
                        "score": (not exact, not ref.startswith("bk.#"), ref.startswith("bio."), len(name))})
        out.sort(key=lambda r: r["score"])
        return out[:limit]

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

    def showcase(self, count=12, seed=None, min_ratings=15):
        """Well-rated books you own but haven't read, one per series/author, rotating daily.

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
        skip_types = ("text.monograph.bible", "text.monograph.lexicon", "text.monograph.dictionary",
                      "text.monograph.encyclopedia", "text.monograph.ancient-manuscript",
                      "text.monograph.ancient-manuscript.translation", "text.monograph.courseware",
                      "text.monograph.grammar", "text.monograph.study.bible", "text.monograph.workbook",
                      "text.monograph.service-book", "text.monograph.cross-references.bible")
        rows = self.db().execute(f"""
            SELECT r.RecordId, r.ResourceId, r.Title, r.Authors, r.Series, r.Type,
                   r.CommunityRating, r.CommunityRatingCount,
                   (SELECT group_concat(AlternateResourceId, ' ') FROM AlternateResourceIds a
                    WHERE a.RecordId = r.RecordId)
            FROM Records r JOIN Images i ON i.RecordId = r.RecordId
            WHERE r.Availability >= 1 AND r.Type LIKE 'text.monograph%'
              AND r.Type NOT IN ({",".join("?" * len(skip_types))})
              AND r.UseCount = 0 AND r.LastAccessed IS NULL
              AND r.CommunityRatingCount >= ? AND i.Image IS NOT NULL""",
            (*skip_types, min_ratings)).fetchall()
        # Bayesian average: books with few ratings are pulled towards the library's mean rating.
        prior = sum(r[6] * r[7] for r in rows) / max(1, sum(r[7] for r in rows))
        weight = 30
        scored = []
        for rec, rid, title, authors, series, typ, rating, n, alts in rows:
            if rid in read:
                continue
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
            names = [" ".join(reversed([x.strip() for x in a.split(",", 1)])) if "," in a else a.strip()
                     for a in re.split(r"[\t;]", authors) if a.strip()]
            byline = names[0] if len(names) == 1 else (f"{names[0]} & {names[1]}" if len(names) == 2
                                                      else f"{names[0]} et al.") if names else ""
            out.append({"title": title, "authors": byline, "series": series,
                        "rating": round(rating, 1), "ratings": n, "resourceId": rid,
                        "url": f"logosres:{logosres_id(rid, alts)}", "cover": self.cover_file(rid)})
        return out

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
        if (!w.normalWindow || w.skipTaskbar) continue;
        if (want.indexOf(c) >= 0 || want.indexOf(n) >= 0) best = w;
    }
    if (best) {
        if (best.minimized) best.minimized = false;
        if ("activeWindow" in workspace) workspace.activeWindow = best;
        else workspace.activeClient = best;
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
            super().__init__(dbus.service.BusName(BUS_NAME, bus), OBJ_PATH)
            self.bus = bus
            self.cfg = Config()
            self.lib = Library()
            self.cmds = {}
            self.token = ""
            self.focus_deadline = 0
            self.focus_script = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "logos-plasma-focus.js"
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
                try:
                    self.bus.get_object("org.kde.klipper", "/klipper", introspect=False).setClipboardContents(
                        match_id, dbus_interface="org.kde.klipper.klipper")
                except dbus.DBusException as e:
                    log(f"clipboard: {e}")
                return
            self.launch(match_id)

        @dbus.service.method(INTERNAL_IFACE)
        def Focus(self):
            self.focus_deadline = time.monotonic() + 5
            GLib.idle_add(self.focus)

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
            url = self.notif_actions.get(int(nid), {}).get(str(action))
            if url:
                self.launch(url)

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
                             actions=["default", "Read now", "open", "Read now"] if url else [],
                             bus=self.bus, timeout=0)
                if nid:
                    self.notif_actions[nid] = {"default": url, "open": url}
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
            flt = flt.lower()
            rows = []
            seen = set()
            for alias, c in sorted(self.cmds.items()):
                if c.bible is not None and not flt:
                    continue  # don't list hundreds of o<abbr>/s<abbr> unless filtering
                text = f"{alias}  —  {c.name}"
                if flt and flt not in text.lower():
                    continue
                if text in seen:
                    continue
                seen.add(text)
                rows.append(("", text, "logos-plasma", LOW, 0.3,
                             props(subtext=f"{alias} <{c.hint}>", actions=NO_ACTIONS)))
            if not flt and self.lib.bibles and self.cfg.settings["bible_aliases"]:
                o, sa = self.cfg.aliases.get("open", "o"), self.cfg.aliases.get("search", "s")
                rows.append(("", f"{o}<bible> / {sa}<bible>  —  any of your {len(self.lib.bibles)} Bibles",
                             "logos-plasma", LOW, 0.29,
                             props(subtext=f"e.g. {o}{self.lib.bibles[0].key}; type 'logos esv' to filter",
                                   actions=NO_ACTIONS)))
            return rows[:40]

        # launching ------------------------------------------------------------
        def launch(self, url):
            s = self.cfg.settings
            ctx = Gio.AppLaunchContext()
            if self.token:
                ctx.setenv("XDG_ACTIVATION_TOKEN", self.token)
                self.token = ""
            info = (Gio.DesktopAppInfo.new(s["handler"]) if s["handler"]
                    else Gio.AppInfo.get_default_for_uri_scheme("logos4"))
            log(f"launching {url}")
            if info is None:
                log("no logos4: handler registered; falling back to xdg-open")
                GLib.spawn_async(["xdg-open", url], flags=GLib.SpawnFlags.SEARCH_PATH)
            else:
                # Ou Dedetai's handler only declares logos4:/libronixdls: and sets
                # Terminal=true; reuse its command line directly so logosres: links work
                # and no terminal window pops up.
                Gio.AppInfo.create_from_commandline(
                    info.get_commandline(), "Logos", Gio.AppInfoCreateFlags.SUPPORTS_URIS
                ).launch_uris([url], ctx)
            if s["focus"]:
                self.focus_deadline = time.monotonic() + 90
                GLib.timeout_add(350, self.focus)   # after KRunner has closed
                GLib.timeout_add(1800, self.focus)  # again once Logos has handled the link

        def focus(self):
            """Ask KWin to raise the topmost Logos window (async; KWin calls back FocusResult)."""
            try:
                js = FOCUS_JS % (json.dumps([c.lower() for c in self.cfg.settings["window_classes"]]),
                                 BUS_NAME, OBJ_PATH, INTERNAL_IFACE)
                self.focus_script.write_text(js)
                kwin_run_script(self.bus, self.focus_script, "logos-plasma-focus")
            except Exception as e:
                log(f"focus via KWin failed: {e}")
            return False  # one-shot GLib timeout

    DBusGMainLoop(set_as_default=True)
    Runner(dbus.SessionBus())
    GLib.MainLoop().run()


FACTBOOK_ICONS = {
    "Man": "im-user", "Woman": "im-user", "SupernaturalBeing": "starred-symbolic",
    "PeopleGroup": "system-users", "City": "mark-location", "OtherPlace": "mark-location",
    "NaturalPlace": "mark-location", "ManMadePlace": "mark-location", "Thing": "package",
    "ClassOfThing": "package", "Event": "view-calendar", "PreachingTheme": "view-media-lyrics",
    "Topic": "tag", "WordSense": "accessories-dictionary", "Culture": "applications-education",
}


def read_clipboard(selection=False):
    """Clipboard (or primary selection) text, via Klipper or wl-paste/xclip."""
    import subprocess
    cmds = ([["wl-paste", "--primary", "--no-newline"], ["xclip", "-o", "-selection", "primary"]]
            if selection else [["wl-paste", "--no-newline"], ["xclip", "-o", "-selection", "clipboard"]])
    if not selection:
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


def cli_lookup(selection=False):
    """Global-shortcut action: open the Bible reference in the clipboard (or selection) in
    Logos; a single word goes to Bible Word Study instead."""
    cfg = Config()
    cfg.maybe_reload()
    s = cfg.settings
    text = read_clipboard(selection).strip()
    refs = find_references(text)
    if refs:
        cli_open(s["reference_url"].replace("{q}", encode(refs[0], ":,.")))
        if len(refs) > 1:
            notify(f"Opened {refs[0]}", "Also in the clipboard: " + ", ".join(refs[1:6]))
        return
    words = text.split()
    if 0 < len(words) <= 2 and len(text) <= 40:
        cli_open(s["wordstudy_url"].replace("{q}", encode(text, "")))
        return
    notify("No Bible reference found",
           ("In: “" + text[:80] + ("…”" if len(text) > 80 else "”")) if text else "The clipboard is empty.")


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


def cli_open(url):
    """Open a Logos URL through the runner service (handler, no terminal, then focus)."""
    import dbus
    try:
        dbus.SessionBus().get_object(BUS_NAME, OBJ_PATH).Run(url, "", dbus_interface=IFACE)
    except dbus.DBusException as e:
        log(f"runner service unavailable ({e}); using xdg-open")
        os.execvp("xdg-open", ["xdg-open", url])


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


def focus_test():
    """Run the focus script once and print what KWin sees. Usage: --focus-test"""
    import dbus
    import dbus.service
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    name = "io.github.FaithlifeCommunity.LogosPlasma.FocusTest"
    loop = GLib.MainLoop()

    class Probe(dbus.service.Object):
        @dbus.service.method(INTERNAL_IFACE)
        def FocusResult(self, found, info=""):
            print("Logos window raised:", bool(found))
            for w in json.loads(info or "[]"):
                print(" ", w)
            if not json.loads(info or "[]"):
                print("  (no window with 'logos' or '.exe' in its class, name or title)")
            loop.quit()

    Probe(dbus.service.BusName(name, bus), OBJ_PATH)
    cfg = Config()
    cfg.maybe_reload()
    js_path = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "logos-plasma-focustest.js"
    js_path.write_text(FOCUS_JS % (json.dumps([c.lower() for c in cfg.settings["window_classes"]]),
                                   name, OBJ_PATH, INTERNAL_IFACE))
    kwin_run_script(bus, js_path, "logos-plasma-focustest")
    GLib.timeout_add(5000, lambda: (print("No reply from KWin within 5 s."), loop.quit()))
    loop.run()


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


if __name__ == "__main__":
    if "--check" in sys.argv:
        check()
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
        print(json.dumps(lib.showcase(count, seed), ensure_ascii=False))
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
