# Test checklist

Run this before a release, and before porting to another desktop: it is the definition of what
the integrations do. Tick items in a copy (or in the release PR) as you go. This list is for
KDE Plasma; GNOME has its own, shorter one in [gnome.md](gnome.md#testing-on-gnome).

**Start here:** install the release being tested, open Logos, then run

    python3 ~/.local/share/logos-plasma/logos_plasma.py --selftest

It checks the Logos data, the installation and the COM registration, and sends every KRunner
command to the plugin exactly as KRunner does. Everything below is what it can't check: whether
the right thing opens in Logos, and how things look.

- [ ] `--selftest` reports all checks passed

## KRunner (Alt+Space)

### Passages
- [ ] `John 3:16` on its own offers "Open John 3:16 in Logos" and opens your preferred Bible
- [ ] `o John 3:16` lists your top Bibles with covers; Enter opens the first, arrows pick another
- [ ] `oesv John 3:16`, `okjv`, `olsb`: per-Bible aliases open that Bible
- [ ] `otc Ruth 1:1` opens Text Comparison of your top Bibles
- [ ] `opg John 1` · `oeg John 1` open the Passage / Exegetical Guide (not "unable to load guide")
- [ ] `oh Mark 2` opens the Gospel Harmony; `ltc` / `ltcs` open their Text Comparison sets

### Searching
- [ ] `s grace`: the first row (Top Bibles) and the per-Bible rows each run the search
- [ ] `stb grace` (Top Bibles) · `sll grace` (whole library; link format unconfirmed)
- [ ] `'Jesus wept` exact phrase · `.God love` all words, any order

### Words and the Factbook
- [ ] `lex ζύμη` follows your Prioritize order and opens at the headword
- [ ] `lex חֶסֶד` offers only Hebrew lexicons
- [ ] `obdag ζύμη` opens BDAG at the headword (link format unconfirmed)
- [ ] `ws agape` opens Bible Word Study
- [ ] `fb jesus` puts Jesus Christ first; `fb moses` lists entries with descriptions and opens the one you pick

### Library, layouts, copying
- [ ] `ol bavinck` lists matching books with covers and opens them
- [ ] `or` lists recently opened books and reopens them at the right place
- [ ] `lay` lists your saved layouts (no "Application Closed" autosaves); `lay dev` filters; Enter switches Logos to it
- [ ] `lay passage Rom 8:28` opens the layout with its linked Bible and commentaries at Romans 8:28 (note whether guides follow)
- [ ] `lay` works when Logos isn't running (the COM API starts it)
- [ ] `cv John 3:16-18` copies the passage in your Copy Bible Verses format; a notification shows it; paste somewhere to check
- [ ] `cv` with Logos closed says it couldn't copy (Logos isn't running)

### Every day
- [ ] `rp` lists today's reading-plan readings and opens them
- [ ] `today` opens your devotional at today's entry

### Discoverability and behaviour
- [ ] `logos` shows grouped help rows that fit on screen, below the Logos app itself (`logos` + Enter still launches Logos)
- [ ] `logos search`, `logos fb` list the matching commands
- [ ] Typing `?` in KRunner lists the Logos commands with descriptions
- [ ] `--check` reports no alias conflicts with programs on your `$PATH`
- [ ] "Copy Logos URL" button on a result puts the link on the clipboard
- [ ] Nothing opens a terminal window (KRunner, widgets, shortcut, reminders)

## Bringing Logos forward
- [ ] From KRunner, a widget and Alt+Shift+L, when Logos is already running
- [ ] When the link starts Logos
- [ ] It stops trying once Logos is in front (no focus-stealing later)

## Look up in Logos (Alt+Shift+L)
- [ ] Copy "…(John 3:16, ESV)" anywhere and press Alt+Shift+L: opens John 3:16
- [ ] With Logos running, select (just highlight) "jn 1v10", "John 1 10" or "Rom 8.28-30" and press Alt+Shift+L: opens it
- [ ] With Logos closed, a plainly written reference (John 1:10) still opens, starting Logos
- [ ] A single copied word opens Bible Word Study
- [ ] Text with no reference shows "No Bible reference found"
- [ ] Listed and changeable in System Settings → Shortcuts → "Look up in Logos"

## Reminders and notifications
- [ ] Reading-plan notifications arrive at each plan's reminder time
- [ ] One "Read now" button; it opens the reading and brings Logos forward
- [ ] Notifications can be dismissed and close after "Read now"
- [ ] Labelled "Logos", with an entry in System Settings → Notifications
- [ ] Optional: `devotional_reminder = "07:30"` sends a daily devotional notification

If notifications misbehave, check which notification server is running: `--selftest` names it.
Another desktop's server (e.g. Xfce Notify Daemon) can take over from Plasma's.

## Reading Plans widget
- [ ] Today / Anytime tabs, covers, streaks, times, overdue labels, progress rings
- [ ] Your devotional row at the top of Today opens today's entry
- [ ] Multi-reading sessions expand; each reading opens
- [ ] Books that aren't downloaded show the cloud icon
- [ ] Updates within 10 minutes of finishing a reading in Logos, and after midnight

## Verse of the Day widget
- [ ] Shows today's art, without text overlay; refreshes after midnight
- [ ] "Crop off the reference footer" crops at the chosen percentage
- [ ] Click opens the verse; the right-click Passage Guide action works
- [ ] Click opens → "A saved layout" opens the named layout

## Showcase widget
- [ ] Settings → Shelf: "Unread and well rated" (default), "Commentaries for your sermon", "Both, half and half"; switching reloads
- [ ] Library shelf: monographs only, nothing you've rated, covers fill the widget and re-flow on resize
- [ ] Sermon shelf: picks your next (or latest) sermon by its date; shows all your 4–5★ commentaries for the passage, 5★ first, scrolling if needed; each opens at the passage
- [ ] Both: even halves; shuffle only changes the library half
- [ ] Right-click → "I've read this, don't show it" hides a book; settings can show hidden books again
- [ ] Hover lift and tilt; shuffle gives a new set; the shelf changes daily
- [ ] Books that aren't downloaded show the cloud badge; clicking a cover opens the book (Logos offers the download)

## Install, update, uninstall
- [ ] The one-command installer installs the latest release; running it again updates
- [ ] Re-running doesn't restart or crash KRunner or Plasma
- [ ] It reports "Logos COM API: registered" (fresh prefix) or "already registered"
- [ ] `sh ~/.local/share/logos-plasma/uninstall.sh` removes the runner, widgets, shortcut and timer, keeping your settings

## Ou Dedetai
- [ ] On Plasma or GNOME with Logos installed and no integrations: the control panel offers the ones for that desktop once; "No" isn't asked again
- [ ] "Yes" installs them; `oudedetai --install-desktop-integrations` installs or updates
- [ ] Not offered on other desktops, with `-y`, or when already installed
