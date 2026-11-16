#!/bin/sh
# Install or update the Logos desktop integrations for the current user.
#   KDE Plasma 6: KRunner commands, Look up in Logos shortcut, reminders, widgets
#   GNOME:        search in the Activities overview, Look up in Logos shortcut, reminders
# Picks the desktop you're running; override with: ./install.sh --plasma | --gnome
# Safe to re-run. Doesn't restart KRunner, plasmashell or GNOME Shell.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
data=${XDG_DATA_HOME:-$HOME/.local/share}
conf=${XDG_CONFIG_HOME:-$HOME/.config}
service=io.github.FaithlifeCommunity.LogosPlasma

case "${1:-}" in
    --plasma|--kde) desktop=plasma ;;
    --gnome) desktop=gnome ;;
    "")
        case ":${XDG_CURRENT_DESKTOP:-}:" in
            *:KDE:*) desktop=plasma ;;
            *:GNOME:*) desktop=gnome ;;
            *) echo "This installs integrations for KDE Plasma or GNOME, and neither seems to be running" >&2
               echo "(XDG_CURRENT_DESKTOP=${XDG_CURRENT_DESKTOP:-unset}). Use --plasma or --gnome to choose." >&2
               exit 1 ;;
        esac ;;
    *) echo "usage: $0 [--plasma | --gnome]" >&2; exit 2 ;;
esac
echo "Installing the Logos integrations for $( [ "$desktop" = plasma ] && echo "KDE Plasma" || echo GNOME )"

/usr/bin/python3 -c 'import dbus, gi, tomllib' 2>/dev/null || {
    echo "Missing Python modules. Ubuntu/Debian: sudo apt install python3-dbus python3-gi" >&2
    echo "  Fedora: sudo dnf install python3-dbus python3-gobject · Arch: sudo pacman -S python-dbus python-gobject" >&2
    exit 1
}
/usr/bin/python3 -c 'import gi; gi.require_version("GdkPixbuf", "2.0")' 2>/dev/null ||
    echo "Note: book covers need gir1.2-gdkpixbuf-2.0 (optional)." >&2

# ── Remove the pre-repo "logos-krunner" versions ─────────────────────────────
if [ "$desktop" = plasma ] && { [ -e "$data/krunner/dbusplugins/logos-krunner.desktop" ] || [ -d "$data/logos-krunner" ]; }; then
    echo "Removing the old logos-krunner install"
    kwriteconfig6 --file krunnerrc --group Plugins --key logos-krunnerEnabled --notify false || true
    pkill -f "$data/logos-krunner/logos_krunner.py" 2>/dev/null || true
    rm -f "$data/krunner/dbusplugins/logos-krunner.desktop" \
          "$data/dbus-1/services/org.kde.logos_krunner.service" \
          "$data"/icons/hicolor/256x256/apps/logos-krunner.*
    rm -rf "$data/logos-krunner"
    kwriteconfig6 --file krunnerrc --group Plugins --key logos-krunnerEnabled --delete || true
fi

# ── Backend + config ─────────────────────────────────────────────────────────
install -Dm755 "$here/backend/logos_plasma.py" "$data/logos-plasma/logos_plasma.py"
install -Dm755 "$here/uninstall.sh" "$data/logos-plasma/uninstall.sh"
install -Dm644 "$here/backend/loadlayout.vbs" "$data/logos-plasma/loadlayout.vbs"
install -Dm644 "$here/backend/copyverses.vbs" "$data/logos-plasma/copyverses.vbs"
install -Dm644 "$here/backend/scanrefs.vbs" "$data/logos-plasma/scanrefs.vbs"
mkdir -p "$conf/logos-plasma"
if [ ! -e "$conf/logos-plasma/commands.toml" ]; then
    if [ -e "$conf/logos-krunner/commands.toml" ] && grep -q '^\[settings\]' "$conf/logos-krunner/commands.toml"; then
        cp "$conf/logos-krunner/commands.toml" "$conf/logos-plasma/commands.toml"
        echo "Carried over your settings from ~/.config/logos-krunner/commands.toml"
    else
        cp "$here/backend/commands.toml" "$conf/logos-plasma/commands.toml"
    fi
else
    cp "$here/backend/commands.toml" "$conf/logos-plasma/commands.toml.new"
    echo "Kept your commands.toml; the latest default is beside it as commands.toml.new"
fi
# Earlier defaults used another user's custom guide names (My_Passage_Guide, …), which
# show "unable to load guide". Switch them to Logos's built-in guides.
if grep -q 't=My_\(Passage_Guide\|Exegetical_Guide\|Bible_Word_Study\)' "$conf/logos-plasma/commands.toml"; then
    cp "$conf/logos-plasma/commands.toml" "$conf/logos-plasma/commands.toml.bak"
    sed -i 's/t=My_Passage_Guide/t=Passage%20Guide/g; s/t=My_Exegetical_Guide/t=Exegetical%20Guide/g; s/t=My_Bible_Word_Study/t=Bible%20Word%20Study/g' \
        "$conf/logos-plasma/commands.toml"
    echo "Updated guide links in commands.toml to Logos's built-in guides (backup: commands.toml.bak)"
fi

# ── The service behind KRunner / GNOME search, started on demand by D-Bus ────
install -Dm644 /dev/stdin "$data/dbus-1/services/$service.service" <<EOF
[D-BUS Service]
Name=$service
Exec=/usr/bin/python3 $data/logos-plasma/logos_plasma.py
EOF

# Borrow the Logos icon from Ou Dedetai's URL handler.
handler=$(xdg-mime query default x-scheme-handler/logos4 2>/dev/null || true)
icon=""
for d in "$data/applications" /usr/share/applications; do
    if [ -n "$handler" ] && [ -f "$d/$handler" ]; then
        icon=$(sed -n 's/^Icon=//p' "$d/$handler" | head -n1)
        break
    fi
done
[ -z "$handler" ] && echo "Warning: nothing handles logos4: links. Run Ou Dedetai's installer first." >&2
if [ -n "$icon" ] && [ -f "$icon" ]; then
    install -Dm644 "$icon" "$data/icons/hicolor/256x256/apps/logos-plasma.${icon##*.}"
fi

# New code takes effect on the next call (D-Bus re-activates the service).
pkill -f "$data/logos-plasma/logos_plasma.py" 2>/dev/null || true

if [ "$desktop" = plasma ]; then
    # ── KRunner runner, with a graceful reload of KRunner and plasmashell's search
    install -Dm644 "$here/krunner/logos-plasma.desktop" "$data/krunner/dbusplugins/logos-plasma.desktop"
    kwriteconfig6 --file krunnerrc --group Plugins --key logos-plasmaEnabled --notify false
    kwriteconfig6 --file krunnerrc --group Plugins --key logos-plasmaEnabled --notify true
fi

# ── App identity for notifications ("Logos" in the popup and in
#    System Settings → Notifications). Launching it just brings Logos forward.
install -Dm644 /dev/stdin "$data/applications/logos-plasma.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Logos
Comment=Logos Bible Software desktop integrations
Icon=logos-plasma
Exec=/usr/bin/python3 $data/logos-plasma/logos_plasma.py --focus
NoDisplay=true
X-GNOME-UsesNotifications=true
EOF

# ── "Look up in Logos" global shortcut (Alt+Shift+L) ─────────────────────────
# Opens the Bible reference in the clipboard in your preferred Bible (a single word goes to
# Bible Word Study). Change the key in System Settings → Shortcuts → "Look up in Logos".
install -Dm644 /dev/stdin "$data/applications/logos-plasma-lookup.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Look up in Logos
Comment=Open the Bible reference in the clipboard in Logos
Icon=logos-plasma
Exec=/usr/bin/python3 $data/logos-plasma/logos_plasma.py --lookup
NoDisplay=false
Categories=Education;
X-KDE-Shortcuts=Alt+Shift+L
Actions=selection;
[Desktop Action selection]
Name=Look up selected text in Logos
Exec=/usr/bin/python3 $data/logos-plasma/logos_plasma.py --lookup --selection
EOF
if [ "$desktop" = plasma ]; then
    # Set the key unless you've chosen one yourself. Plasma clears a key that's already taken
    # (Meta+Alt+L was, on some systems), leaving "_launch=" empty: that counts as unset.
    current=$(kreadconfig6 --file kglobalshortcutsrc --group services --group logos-plasma-lookup.desktop \
        --key _launch 2>/dev/null || true)
    if [ -z "$current" ]; then
        kwriteconfig6 --file kglobalshortcutsrc --group services --group logos-plasma-lookup.desktop \
            --key _launch "Alt+Shift+L" || true
    fi
else
    # GNOME: a custom keyboard shortcut, as in Settings → Keyboard → Custom Shortcuts
    /usr/bin/python3 "$data/logos-plasma/logos_plasma.py" --gnome-shortcut install || true
fi

# Reading what you've highlighted (not just copied) needs wl-paste (Wayland) or xclip (X11)
if ! command -v wl-paste >/dev/null 2>&1 && ! command -v xclip >/dev/null 2>&1; then
    echo "Note: install wl-clipboard (e.g. sudo apt install wl-clipboard) so Alt+Shift+L can look up"
    echo "      highlighted text; without it, it only looks up what you've copied."
fi
[ "$desktop" = plasma ] && { kbuildsycoca6 >/dev/null 2>&1 || true; }

# ── GNOME: search in the Activities overview ─────────────────────────────────
if [ "$desktop" = gnome ]; then
    # GNOME Shell only reads search providers from the system data folders (XDG_DATA_DIRS),
    # not your home folder, so add a folder of ours to that list for your session. It takes
    # effect the next time you log in.
    shared="$data/logos-plasma/gnome-shell-data"
    # Show the results under Ou Dedetai's Logos launcher (its name and icon), if we can find it
    app=$(grep -l -- "--run-installed-app" "$data"/applications/*.desktop 2>/dev/null | head -n1 || true)
    app=${app:+$(basename "$app")}
    install -Dm644 /dev/stdin "$shared/gnome-shell/search-providers/$service.search-provider.ini" <<EOF
[Shell Search Provider]
DesktopId=${app:-logos-plasma-lookup.desktop}
BusName=$service
ObjectPath=/searchprovider
Version=2
EOF
    envfile="$conf/environment.d/60-logos-desktop-integrations.conf"
    if [ ! -e "$envfile" ]; then
        install -Dm644 /dev/stdin "$envfile" <<EOF
# Lets GNOME Shell find the Logos search provider (logos-desktop-integrations)
XDG_DATA_DIRS=\${XDG_DATA_DIRS:-/usr/local/share:/usr/share}:$shared
EOF
        gnome_relogin=1
    fi
fi

# ── Reading-plan reminders (systemd user timer, every 5 minutes) ──────────────
install -Dm644 /dev/stdin "$conf/systemd/user/logos-plasma-reminders.service" <<EOF
[Unit]
Description=Logos reading-plan reminders

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 $data/logos-plasma/logos_plasma.py --check-reminders
EOF
install -Dm644 /dev/stdin "$conf/systemd/user/logos-plasma-reminders.timer" <<EOF
[Unit]
Description=Check Logos reading-plan reminders

[Timer]
OnCalendar=*:0/5
Persistent=false

[Install]
WantedBy=timers.target
EOF
systemctl --user daemon-reload && systemctl --user enable --now logos-plasma-reminders.timer >/dev/null 2>&1 ||
    echo "Note: couldn't enable the reminders timer (systemctl --user)." >&2

# ── Widgets (Plasma) ─────────────────────────────────────────────────────────
if [ "$desktop" = plasma ]; then
    for w in verse-of-the-day reading-plans showcase; do
        tmp=$(mktemp -d)
        cp -r "$here/plasmoids/$w/." "$tmp/"
        cp "$here/plasmoids/shared/Backend.qml" "$tmp/contents/ui/Backend.qml"
        kpackagetool6 -t Plasma/Applet --upgrade "$tmp" >/dev/null 2>&1 ||
            kpackagetool6 -t Plasma/Applet --install "$tmp"
        rm -rf "$tmp"
    done
fi

# Logos's COM API (used to open saved layouts) is registered per-user, where Wine doesn't
# look; copy its registration machine-wide in the Logos prefix. Harmless if already done.
/usr/bin/python3 "$data/logos-plasma/logos_plasma.py" --register-com || true
/usr/bin/python3 "$data/logos-plasma/logos_plasma.py" --check
if [ "$desktop" = gnome ]; then
    cat <<'EOF'

Done.
  Search: press Super and type  John 3:16 · cv John 3:16 · fb moses · today · rp · logos
  Select or copy a reference anywhere, then Alt+Shift+L to open it in Logos.
  Change the key in Settings → Keyboard → Keyboard Shortcuts → Custom Shortcuts.
  Check everything:  python3 ~/.local/share/logos-plasma/logos_plasma.py --selftest
  Uninstall:         sh ~/.local/share/logos-plasma/uninstall.sh
EOF
    [ "${gnome_relogin:-}" = 1 ] && echo "  Log out and back in once so GNOME's search finds Logos."
    exit 0
fi
cat <<'EOF'

Done.
  KRunner (Alt+Space):  John 3:16 · o John 3:16 · s grace · fb moses · today · rp · logos
  Select or copy a reference anywhere, then Alt+Shift+L to open it in Logos (may need a re-login the first time).
  Widgets: right-click the desktop or panel → Add Widgets → search "Logos".
  If an updated widget still looks old: systemctl --user restart plasma-plasmashell
  Check everything:  python3 ~/.local/share/logos-plasma/logos_plasma.py --selftest
  Uninstall:         sh ~/.local/share/logos-plasma/uninstall.sh
EOF
