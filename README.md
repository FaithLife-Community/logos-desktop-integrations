# Logos desktop integrations

Desktop integrations for [Logos Bible Software](https://www.logos.com) running on Linux under
Wine via [Ou Dedetai](https://github.com/FaithLife-Community/OuDedetai), for **KDE Plasma 6** and
**GNOME**. The installer picks the one you're running.

**On GNOME** you get the same commands in the Activities overview search, the Alt+Shift+L
look-up shortcut, and reading-plan reminders; there are no widgets. See [GNOME](docs/gnome.md).

**On macOS:** native widgets, Spotlight, Siri/Shortcuts and Services are under development on a separate branch. See [macOS](macos/README.md) for building and signing, including the option to compile out Logos-folder access.

**On KDE Plasma:**

* **KRunner commands**: a Raycast/BibleWorks-style command line for Logos, available in
  KRunner (Alt+Space) and Plasma's launcher search. See the [KRunner guide](docs/krunner.md).
* **Logos Verse of the Day** widget: today's Verse of the Day art. Click it to open the verse in Logos.
* **Logos Showcase** widget: a shelf of well-rated books you own but haven't read on any
  device, one per series and author, refreshed daily. Covers lift and tilt as you hover.
  Set a Showcase to **Commentaries for your sermon** instead and it shows the commentaries
  you've rated 4–5★ for the passage of your next sermon document, each opening at that passage,
  or to **Both, half and half**.
* **Look up in Logos** (Alt+Shift+L): copy a Bible reference anywhere and open it in your
  preferred Bible. A single word opens Bible Word Study instead.
* **Reading-plan reminders**: notifications at each plan's reminder time, with a "Read now" button.
* **Logos Reading Plans** widget: styled after the Reading Plans card on Logos's home page, plus your devotional.
  It has Today/Anytime tabs, covers, streaks, estimated reading times, overdue labels and
  progress rings. Click a plan to open its next reading.

Everything opens in your running Logos and, on Plasma, brings its window to the front.

> Community project, not affiliated with or supported by Faithlife.

## Install

Requires Plasma 6 or GNOME, Ou Dedetai (which registers the `logos4:` link handler) and
`python3-dbus` / `python3-gi` (`gir1.2-gdkpixbuf-2.0` for book covers), and `wl-clipboard` so the look-up shortcut can read highlighted text.
On GNOME, log out and back in once after the first install so its search finds Logos.

Install or update with one command:

    curl -fsSL https://raw.githubusercontent.com/FaithLife-Community/logos-desktop-integrations/main/get.sh | sh

This downloads the latest release and runs its `install.sh`; run it again to update (Ou Dedetai also offers updates). Or from a clone:

    git clone https://github.com/FaithLife-Community/logos-desktop-integrations
    cd logos-desktop-integrations
    ./install.sh

To uninstall: `sh ~/.local/share/logos-plasma/uninstall.sh` (removes everything except your
settings in `~/.config/logos-plasma`). The installer doesn't restart KRunner, Plasma or GNOME Shell.
To choose the desktop yourself: `./install.sh --plasma` or `./install.sh --gnome`.

## Commands (KRunner and GNOME search)

| Type | Does |
|---|---|
| `o John 3:16` | Open a passage. Your top Bibles are listed with covers; Enter opens the first |
| `o lsb John 3:16` · `olsb John 3:16` | …in a specific Bible: `o` + the abbreviation of any Bible you own |
| `s grace` · `sesv grace` | Search: pick Top Bibles or a Bible, or name one |
| `stb grace` · `sll grace` | Search Logos's Top Bibles · search your whole library |
| `'Jesus wept` · `.God love` | BibleWorks-style exact phrase / words in any order |
| `lex ἀγάπη` · `obdag ἀγάπη` | Look a word up in your prioritized Greek or Hebrew lexicons, or in a named one |
| `ol bavinck` | Open any book in your library by title, author or abbreviation |
| `otc Ruth 1:1` | Text Comparison of your top Bibles |
| `opg` `oeg` `obws` `oh` `ltc` `ltcs` | Passage/Exegetical Guide, Bible Word Study, Gospel Harmony, Text Comparisons |
| `rp` | Today's readings from your reading plans |
| `today` | Today's entry in your devotionals |
| `ws agape` · `fb moses` | Bible Word Study · Factbook, with Logos's own descriptions to tell same-named entries apart |
| `or` | Recently opened books |
| `lay` | Your saved layouts: switch Logos to one |
| `cv John 3:16` | Copy a passage as text, in your Copy Bible Verses style |
| `John 3:16` | A bare reference opens in your preferred Bible |
| `logos [filter]` | List commands |

Aliases, picker Bibles and your own URL commands live in `~/.config/logos-plasma/commands.toml`.
To add a command, use **Copy location** on a Logos panel and replace the passage or word with `{q}`.
The [KRunner guide](docs/krunner.md) covers every command in more detail, and [docs/testing.md](docs/testing.md) is the full test checklist ([GNOME's](docs/gnome.md#testing-on-gnome)).

## How it works

See [docs/how-it-works.md](docs/how-it-works.md) for the files the backend reads, the link
formats, and how it gets around the handler's limitations.

## Troubleshooting

    python3 ~/.local/share/logos-plasma/logos_plasma.py --selftest     # check everything; add --live to open Logos too
    python3 ~/.local/share/logos-plasma/logos_plasma.py --check        # paths, Bibles, alias conflicts
    python3 ~/.local/share/logos-plasma/logos_plasma.py --focus-test   # what KWin sees when raising Logos
    python3 ~/.local/share/logos-plasma/logos_plasma.py --reading-plans
    journalctl --user -f | grep logos-plasma

`--selftest` writes its report to `~/.local/share/logos-plasma/selftest.txt`; attach that
file when reporting a problem.

If Logos isn't brought to the front, `--focus-test` lists the candidate windows. Put the
right class in `window_classes` in `commands.toml`.

## Licence

GPL-3.0-or-later
