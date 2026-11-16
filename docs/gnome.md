# GNOME

On GNOME the integrations use GNOME's own pieces rather than copying Plasma's:

* **Search in the Activities overview.** Press Super and type, just as in KRunner: `John 3:16`,
  `o John 3:16`, `s grace`, `cv John 3:16`, `fb moses`, `lay`, `today`, `rp`, `logos` for the list.
  Results appear under Logos's own name and icon, and Enter or a click opens the top one. Every
  command in the [KRunner guide](krunner.md) works here, from the same backend.
* **Look up in Logos (Alt+Shift+L).** Select or copy a reference in any app and press the key.
  It's an ordinary custom shortcut: change it in Settings → Keyboard → Keyboard Shortcuts → Custom
  Shortcuts. If Alt+Shift+L is already in use, the installer leaves the key blank for you to choose.
* **Reading-plan reminders**, as GNOME notifications with a "Read now" button.

There are no widgets: GNOME doesn't have desktop or panel widgets, and the integrations don't add an
extension to fake them.

## Differences from Plasma

* **Logos doesn't jump to the front.** When something opens in Logos while it's behind other windows,
  GNOME shows "Logos is ready"; click it to switch. That's how GNOME treats every app. On Plasma a
  small KWin script brings Logos forward instead. Logos's own "activate window" call doesn't get past
  KWin or GNOME, and a GNOME Shell extension just for this isn't worth the upkeep yet.
* **GNOME shows about five results per app**, and no extra buttons on a result. So `o John 3:16`
  shows your top few Bibles, and there's no "Copy Logos URL" button.
* **Log out and back in once after the first install.** GNOME only looks for search providers in
  system folders, so the installer adds one of its own folders to that list for your session
  (`~/.config/environment.d/60-logos-desktop-integrations.conf`). That takes effect at your next login.
  The self-test says whether it has.

To hide Logos from search without uninstalling, turn it off in Settings → Search.

## Requirements

Ou Dedetai with Logos installed, and Python 3.11+ with D-Bus and GObject bindings:

* Ubuntu / Debian: `sudo apt install python3-dbus python3-gi gir1.2-gdkpixbuf-2.0 wl-clipboard`
* Fedora: `sudo dnf install python3-dbus python3-gobject wl-clipboard`
* Arch: `sudo pacman -S python-dbus python-gobject wl-clipboard`

`wl-clipboard` is what lets the shortcut read highlighted text, not only copied text (`xclip` on X11).

## Testing on GNOME

On a GNOME machine, a virtual machine, or a live USB with Ou Dedetai and Logos installed:

    curl -fsSL https://raw.githubusercontent.com/FaithLife-Community/logos-desktop-integrations/main/get.sh | sh

Log out and back in, open Logos, then run

    python3 ~/.local/share/logos-plasma/logos_plasma.py --selftest

and send `~/.local/share/logos-plasma/selftest.txt` along with your ticks below. To test a branch
before it's released, clone it and run `./install.sh` instead (add `--gnome` if your session doesn't
report GNOME, e.g. some Ubuntu variants).

- [ ] `--selftest` passes, including "GNOME search can see it in this session" and the live search checks
- [ ] Settings → Search lists Logos, switched on
- [ ] Super, `John 3:16`: a Logos result opens John 3:16 in your preferred Bible
- [ ] With Logos behind another window: "Logos is ready" appears, and clicking it switches to Logos
- [ ] When the search starts Logos, it opens at the passage once loaded
- [ ] `o John 3:16` lists Bibles (with covers); `s grace` runs a search; `fb moses` opens a Factbook entry
- [ ] `lay` lists your saved layouts and opens one; `lay passage John 3:16` opens it at the verse
- [ ] `cv John 3:16`: a notification says it's copied, and pasting gives the verse text
- [ ] `today` and `rp` list your devotional and readings and open them
- [ ] `logos` lists the commands; clicking Logos's icon beside its results searches Logos for the words
- [ ] Settings → Keyboard → Custom Shortcuts has "Look up in Logos" on Alt+Shift+L
- [ ] Copy "(John 3:16, ESV)" anywhere, press Alt+Shift+L: opens John 3:16
- [ ] Highlight (don't copy) "Rom 8.28-30" in a browser or text editor, press Alt+Shift+L: opens it
- [ ] A single copied word opens Bible Word Study; text with no reference says "No Bible reference found"
- [ ] A reading-plan reminder arrives (set one a few minutes ahead in Logos); "Read now" opens it
- [ ] Notifications are labelled "Logos" and can be dismissed
- [ ] Nothing opens a terminal window
- [ ] `sh ~/.local/share/logos-plasma/uninstall.sh` removes the shortcut, and after logging out and in, the search results

Worth noting if they happen: the screen flickering when the shortcut reads the selection (wl-paste
needs a moment of focus on GNOME), and which GNOME version and distribution you tested
(`gnome-shell --version`).
