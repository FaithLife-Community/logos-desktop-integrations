# How it works

## Opening things in Logos

Logos understands `logos4:` and `logosres:` URLs; they're the same links behind Logos's
own **Copy location** and `ref.ly` links. For example:

    logosres:esv;ref=BibleESV.John 3:16
    logos4:Guide;t=My_Passage_Guide;ref=BibleESV.Ro6.4
    logos4:Search;kind=MorphSearch;q=grace;in=raw:Single|ResourceId=LLS:1.0.710

Ou Dedetai registers a desktop handler for `logos4:` (and `libronixdls:`). The backend reads
that handler's command line and runs it directly instead of going through `xdg-open`. That has
two benefits:

* `logosres:` links work too. The handler doesn't declare that scheme, but Logos.exe accepts it.
* No terminal opens. The handler sets `Terminal=true` so login-flow errors are visible.

Fixing both in Ou Dedetai's handler would let plain `xdg-open` work as well.

After opening a link, the backend loads a small KWin script over D-Bus. The script
unminimizes and activates the topmost Logos window. KRunner's XDG activation token can't
be handed on to a Wine window, so this is the only reliable way to raise it on Wayland.

## What the backend reads

Everything is read **read-only** from Logos's local SQLite databases inside the Ou Dedetai
Wine prefix (`…/AppData/Local/Logos`). Nothing is written, decrypted or decompiled. Book
content stays in Logos's own encrypted resource files, which this project never opens.

| File | Used for |
|---|---|
| `Data/<user>/LibraryCatalog/catalog.db` | Your books: titles, abbreviations, resource IDs, link IDs, usage counts, cover thumbnails |
| `Documents/<user>/KeyLinkManager/KeyLinkSyncManager.db` | Your **Prioritize** order: top Bibles, lexicons |
| `Documents/<user>/Documents/ReadingPlan/ReadingPlan.db` | Reading plan schedules and which sessions you've completed |

The schemas aren't documented and may change with Logos updates. The code reads them
defensively and degrades gracefully.

The Verse of the Day widget fetches the public page `https://biblia.com/verseoftheday`.
That's the same verse and art Logos's home page shows. The widget reads the page's image
and its "Read in Logos" link.

## Reading plans

Each plan document stores its sessions as JSON (`[{date, title, readings: [[{resourceId,
reference | textRange}]]}]`). Its status row stores completed sessions as ranges (`0-179`).
The two are linked by a GUID: the document stores .NET byte order, the status stores plain hex.
The next session is the first one that isn't complete. Bible readings open at their reference;
book readings open the book.

The widget shows the same details as Logos's own card:

* **Streak**: consecutive days with a completed session (from each session's `completedDate`).
* **Progress ring**: completed sessions ÷ total; red when the plan is behind schedule.
* **Today / Anytime**: dated plans versus self-paced ones (start date `1900-01-01`),
  including plans you haven't started yet.
* **Reading time**: Logos's per-word counts come from encrypted resources, so the backend
  estimates instead. Bible readings use verses ÷ 10.4 per minute; book readings use
  text-range length ÷ 1475 per minute. Both rates are calibrated against Logos's own
  estimates. Readings spanning non-adjacent chapters can't be measured, so they show no time.
