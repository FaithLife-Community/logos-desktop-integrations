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

# ── Widgets ──────────────────────────────────────────────────────────────────
for w in verse-of-the-day reading-plans; do
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
  KRunner (Alt+Space):  o John 3:16 · s grace · rp · logos
  Widgets: right-click the desktop or panel → Add Widgets → search "Logos".
  If an updated widget still looks old: systemctl --user restart plasma-plasmashell
EOF
