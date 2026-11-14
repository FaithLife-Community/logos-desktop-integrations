#!/bin/sh
# Install or update Logos Plasma integrations for the current user (Plasma 6):
#   - backend + KRunner runner (D-Bus service io.github.FaithlifeCommunity.LogosPlasma)
#   - Plasma widgets: Logos Verse of the Day, Logos Reading Plans
# Safe to re-run. Doesn't restart KRunner or plasmashell.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
data=${XDG_DATA_HOME:-$HOME/.local/share}
conf=${XDG_CONFIG_HOME:-$HOME/.config}
service=io.github.FaithlifeCommunity.LogosPlasma

/usr/bin/python3 -c 'import dbus, gi, tomllib' 2>/dev/null || {
    echo "Missing Python modules. On Kubuntu/Debian: sudo apt install python3-dbus python3-gi" >&2
    exit 1
}
/usr/bin/python3 -c 'import gi; gi.require_version("GdkPixbuf", "2.0")' 2>/dev/null ||
    echo "Note: book covers need gir1.2-gdkpixbuf-2.0 (optional)." >&2

# ── Remove the pre-repo "logos-krunner" versions ─────────────────────────────
if [ -e "$data/krunner/dbusplugins/logos-krunner.desktop" ] || [ -d "$data/logos-krunner" ]; then
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

# ── KRunner runner ───────────────────────────────────────────────────────────
install -Dm644 "$here/krunner/logos-plasma.desktop" "$data/krunner/dbusplugins/logos-plasma.desktop"
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

# Graceful reload of KRunner and plasmashell's search.
kwriteconfig6 --file krunnerrc --group Plugins --key logos-plasmaEnabled --notify false
kwriteconfig6 --file krunnerrc --group Plugins --key logos-plasmaEnabled --notify true

# ── App identity for notifications ("Logos" in the popup and in
#    System Settings → Notifications). Launching it just brings Logos forward.
install -Dm644 /dev/stdin "$data/applications/logos-plasma.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Logos
Comment=Logos Bible Software integrations for Plasma
Icon=logos-plasma
Exec=/usr/bin/python3 $data/logos-plasma/logos_plasma.py --focus
NoDisplay=true
X-GNOME-UsesNotifications=true
EOF

# ── "Look up in Logos" global shortcut (Meta+Alt+L) ─────────────────────────
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
X-KDE-Shortcuts=Meta+Alt+L
Actions=selection;
[Desktop Action selection]
Name=Look up selected text in Logos
Exec=/usr/bin/python3 $data/logos-plasma/logos_plasma.py --lookup --selection
EOF
if ! grep -q 'logos-plasma-lookup.desktop' "$conf/kglobalshortcutsrc" 2>/dev/null; then
    kwriteconfig6 --file kglobalshortcutsrc --group services --group logos-plasma-lookup.desktop \
        --key _launch "Meta+Alt+L" || true
fi
kbuildsycoca6 >/dev/null 2>&1 || true

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

# ── Widgets ──────────────────────────────────────────────────────────────────
for w in verse-of-the-day reading-plans showcase; do
    tmp=$(mktemp -d)
    cp -r "$here/plasmoids/$w/." "$tmp/"
    cp "$here/plasmoids/shared/Backend.qml" "$tmp/contents/ui/Backend.qml"
    kpackagetool6 -t Plasma/Applet --upgrade "$tmp" >/dev/null 2>&1 ||
        kpackagetool6 -t Plasma/Applet --install "$tmp"
    rm -rf "$tmp"
done

/usr/bin/python3 "$data/logos-plasma/logos_plasma.py" --check
cat <<'EOF'

Done.
  KRunner (Alt+Space):  John 3:16 · o John 3:16 · s grace · fb moses · today · rp · logos
  Copy a reference anywhere, then Meta+Alt+L to open it in Logos (may need a re-login the first time).
  Widgets: right-click the desktop or panel → Add Widgets → search "Logos".
  If an updated widget still looks old: systemctl --user restart plasma-plasmashell
  Check everything:  python3 ~/.local/share/logos-plasma/logos_plasma.py --selftest
  Uninstall:         sh ~/.local/share/logos-plasma/uninstall.sh
EOF
