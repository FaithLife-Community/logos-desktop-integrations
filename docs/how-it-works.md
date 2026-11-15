# How it works

## Opening things in Logos

Logos understands `logos4:` and `logosres:` URLs; they're the same links behind Logos's
own **Copy location** and `ref.ly` links. For example:

    logosres:esv;ref=BibleESV.John 3:16
    logos4:Guide;t=Passage%20Guide;ref=BibleESV.Ro6.4
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
| `Documents/<user>/Documents/ReadingPlan/ReadingPlan.db` | Reading plan schedules, completed sessions, reminder times |
| `Data/<user>/KeyLinkManager/keylinkmanager.db` | The Prioritize order Logos currently uses (lower rank = higher) |
| `Data/<user>/ReadingProgressManager/readingprogressmanager.db` | Synced reading progress, so the showcase skips books read on any device |
| `Data/<user>/AutoComplete/AutoComplete.db` | Factbook names, aliases and descriptions for `fb` |
| `Data/<user>/HistoryManager/history.db` | Recently opened books for `or` |

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

## Showcase

Candidates are monographs you own that have a cover and at least 15 community ratings, and
that you haven't opened on any device: no synced reading progress, no local use count. They're
ranked by a Bayesian average, which pulls books with few ratings towards your library's mean,
so a 5.0 from two readers doesn't beat 4.4 from four hundred. The shelf takes at most one book
per series and per first author, and no more than a third commentaries. It's a daily shuffle
of the top 36.

## Reminders

A systemd user timer runs `logos_plasma.py --check-reminders` every five minutes. The runner
service sends one notification per plan per day, once the plan's reminder time (set in Logos)
has passed and its next session is due. The service handles the notification's "Read now"
button. Which plans have been reminded is stored in `~/.local/state/logos-plasma/reminders.json`.

## Layouts

Logos has no link for opening a layout, but its documented COM API has
`LoadLayout(name)`. `lay` in KRunner and the Verse of the Day widget's "A saved layout" option
run a small VBScript (`loadlayout.vbs`) with `cscript` inside the Logos Wine prefix, through
Ou Dedetai's `--wine`. The list of layouts is read from `LayoutManager/layouts.db`.

Logos registers its COM server (`LogosCom.exe`) for the current user only
(`HKEY_CURRENT_USER\Software\Classes`), and Wine looks COM classes up machine-wide, so
`CreateObject` fails with "ActiveX component can't create object". The installer runs
`logos_plasma.py --register-com`, which copies Logos's own registration, unchanged, from the
prefix's `user.reg` to `HKEY_LOCAL_MACHINE\Software\Classes` (via `regedit /S`; the file it
imports is kept as `~/.local/share/logos-plasma/logos-com-hklm.reg`).

## Copying verses

`cv` uses the same COM API: `CopyBibleVerses.GetText` returns the passage in your preferred
Bible, formatted the way you last set up Logos's Copy Bible Verses tool. `copyverses.vbs` writes it
to `copyverses.txt` as UTF-16 (Wine's console output would mangle Greek, Hebrew and curly quotes),
and the backend puts it on the clipboard.

### Passing objects to Logos under Wine

Calls that take a request object (`CopyBibleVerses.GetText`, `Panel.Navigate`) fail under Wine
with VBScript error 5, "Invalid procedure call or argument", when the object is passed by
reference (VBScript's default). Passing it by value, in extra parentheses such as
`GetText((req))`, works. This looks like a Wine marshalling bug with by-reference
`VT_DISPATCH` arguments across processes.
