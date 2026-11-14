# Logos Plasma integrations

KDE Plasma 6 integrations for [Logos Bible Software](https://www.logos.com) running on Linux
under Wine via [Ou Dedetai](https://github.com/FaithLife-Community/OuDedetai):

* **KRunner commands**: a Raycast/BibleWorks-style command line for Logos, available in
  KRunner (Alt+Space) and Plasma's launcher search.
* **Logos Verse of the Day** widget: today's Verse of the Day art. Click it to open the verse in Logos.
* **Logos Reading Plans** widget: styled after the Reading Plans card on Logos's home page.
  It has Today/Anytime tabs, covers, streaks, estimated reading times, overdue labels and
  progress rings. Click a plan to open its next reading.

Everything opens in your running Logos and brings its window to the front.

> Community project, not affiliated with or supported by Faithlife.

## Install

Requires Plasma 6, Ou Dedetai (which registers the `logos4:` link handler) and
`python3-dbus` / `python3-gi` (`gir1.2-gdkpixbuf-2.0` for book covers).

    git clone https://github.com/FaithLife-Community/logos-plasma-integrations
    cd logos-plasma-integrations
    ./install.sh

Re-run `./install.sh` to update. `./uninstall.sh` removes everything except your settings.
The installer doesn't restart KRunner or Plasma.

## KRunner commands

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
| `logos [filter]` | List commands |

Aliases, picker Bibles and your own URL commands live in `~/.config/logos-plasma/commands.toml`.
To add a command, use **Copy location** on a Logos panel and replace the passage or word with `{q}`.

## How it works

See [docs/how-it-works.md](docs/how-it-works.md) for the files the backend reads, the link
formats, and how it gets around the handler's limitations.

## Troubleshooting

    python3 ~/.local/share/logos-plasma/logos_plasma.py --check        # paths, Bibles, alias conflicts
    python3 ~/.local/share/logos-plasma/logos_plasma.py --focus-test   # what KWin sees when raising Logos
    python3 ~/.local/share/logos-plasma/logos_plasma.py --reading-plans
    journalctl --user -f | grep logos-plasma

If Logos isn't brought to the front, `--focus-test` lists the candidate windows. Put the
right class in `window_classes` in `commands.toml`.

## Licence

GPL-3.0-or-later
