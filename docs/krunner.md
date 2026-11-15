# KRunner guide

Press **Alt+Space** (or start typing in the Plasma launcher) and type a command. Every command
opens in your running Logos and brings it to the front; if Logos isn't running, it starts.

Type **`logos`** to see a summary of the commands, or **`logos <word>`** (for example
`logos search`) to list the commands that match. `logos` + Enter still launches Logos itself.

All the short names (aliases) can be changed or switched off in
`~/.config/logos-plasma/commands.toml`. Changes apply on your next keystroke.

## Opening passages

| Type | What happens |
|---|---|
| `John 3:16` | Any Bible reference on its own opens in **your preferred Bible** (the one set in Logos). Several references (`Gen 1:1; John 1:1`) give one row each. |
| `o John 3:16` | Lists your top Bibles, with covers. Enter opens the first; pick another with the arrow keys. |
| `o lsb John 3:16` | Names the Bible after `o`. |
| `oesv John 3:16` | `o` + the abbreviation of **any Bible you own** (`okjv`, `olsb`, `onasb95`…). |
| `otc Ruth 1:1` | Text Comparison of your top Bibles. |
| `opg John 1` · `oeg John 1` | Passage Guide · Exegetical Guide. |
| `oh Mark 2` | Gospel Harmony. |
| `ltc Ruth 1:1` · `ltcs Ruth 1:1` | Text Comparison of a fixed English set · Hebrew/Greek/Latin set. |

Your top Bibles are the ones you open most, or follow Logos's **Prioritize** list if you set
`picker_order = "priority"`; you can also list them yourself with `picker_bibles`.

## Searching

| Type | What happens |
|---|---|
| `s grace` | Pick where to search: Top Bibles first, then each of your top Bibles. |
| `sesv grace` | Search one Bible (`s` + its abbreviation). |
| `stb grace` | Logos's Top Bibles search. |
| `sll grace` | Search your whole library. |
| `'Jesus wept` | Exact phrase. |
| `.God love` | All the words, in any order. |

## Words, lexicons and the Factbook

| Type | What happens |
|---|---|
| `lex ἀγάπη` | Your lexicons for that language, in your **Prioritize** order, opened at the headword. Hebrew words offer only Hebrew lexicons. |
| `obdag ἀγάπη` | `o` + a lexicon's abbreviation opens that lexicon at the headword. |
| `ws agape` | Bible Word Study. |
| `fb moses` | The Factbook: matching people, places and topics with Logos's own descriptions, best match first. Pick one to open it. |

## Your library

| Type | What happens |
|---|---|
| `ol bavinck` | Open a book by title, author or abbreviation (with covers). |
| `or` | Books you opened recently; Enter reopens one. `or calvin` filters them. |
| `lay` | Your saved layouts; Enter switches Logos to one. `lay sermon` filters them. |
| `lay passage John 3:16` | Opens a layout with its Bible (and everything linked to it) at that passage. |

## Every day

| Type | What happens |
|---|---|
| `rp` | Today's readings from your reading plans. |
| `today` | Today's entry in your devotionals (your prioritized ones first). |
| **Alt+Shift+L** (anywhere) | Opens the Bible reference you've selected (or copied) in any app. "jn 1v10", "John 1 10", ranges and lists all work; anything our parser doesn't recognise is passed to Logos's own parser if Logos is running. A single word opens Bible Word Study. Change the key in System Settings → Shortcuts → "Look up in Logos". |

## Copying verses

| Type | What happens |
|---|---|
| `cv John 3:16-18` | Copies the passage as text to the clipboard, in your preferred Bible and the format you last chose in Logos's **Copy Bible Verses** tool. Logos needs to be running. |

## Extra actions

Each result has a **Copy Logos URL** button (shown when you hover or select it), which puts the
link on the clipboard so you can paste it into notes or documents.

## Adding your own commands

In Logos, open the panel you want, choose **Copy location** from the panel menu, then add it to
`commands.toml` with `{q}` where the passage or word goes:

```toml
[[command]]
alias = "oh"
name = "Gospel Harmony"
hint = "a passage"
url = 'logosres:hrmnysyngspl;ref=Bible.{q}'
```

Your own commands win over the built-in and per-Bible aliases.

## If something doesn't work

Run `python3 ~/.local/share/logos-plasma/logos_plasma.py --selftest`. It sends every command
above to the plugin exactly as KRunner does and reports what comes back. `--check` also lists
any alias that clashes with a program on your `$PATH` (KRunner's Shell runner would then offer
both).
