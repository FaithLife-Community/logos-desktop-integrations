#!/bin/sh
# Remove the Logos desktop integrations (KDE Plasma and/or GNOME parts, whichever are
# installed). Leaves your settings in ~/.config/logos-plasma alone.
data=${XDG_DATA_HOME:-$HOME/.local/share}
conf=${XDG_CONFIG_HOME:-$HOME/.config}
lp="$data/logos-plasma/logos_plasma.py"
have() { command -v "$1" >/dev/null 2>&1; }

have kwriteconfig6 && kwriteconfig6 --file krunnerrc --group Plugins --key logos-plasmaEnabled --notify false
# GNOME: the custom shortcut (needs the backend, so before it's removed)
[ -f "$lp" ] && have gsettings && /usr/bin/python3 "$lp" --gnome-shortcut remove >/dev/null 2>&1
pkill -f "$lp" 2>/dev/null
rm -f "$data/krunner/dbusplugins/logos-plasma.desktop" \
      "$data/dbus-1/services/io.github.FaithlifeCommunity.LogosPlasma.service" \
      "$data"/icons/hicolor/256x256/apps/logos-plasma.* \
      "$conf/environment.d/60-logos-desktop-integrations.conf"
rm -rf "$data/logos-plasma"
systemctl --user disable --now logos-plasma-reminders.timer >/dev/null 2>&1
rm -f "$conf"/systemd/user/logos-plasma-reminders.* \
      "$data/applications/logos-plasma-lookup.desktop" "$data/applications/logos-plasma.desktop"
if have kwriteconfig6; then
    kwriteconfig6 --file kglobalshortcutsrc --group services --group logos-plasma-lookup.desktop --key _launch --delete
    kbuildsycoca6 >/dev/null 2>&1
    kwriteconfig6 --file krunnerrc --group Plugins --key logos-plasmaEnabled --delete
    for id in io.github.FaithlifeCommunity.LogosVerseOfTheDay io.github.FaithlifeCommunity.LogosReadingPlans io.github.FaithlifeCommunity.LogosShowcase; do
        kpackagetool6 -t Plasma/Applet --remove "$id" >/dev/null 2>&1
    done
    echo "Removed. (Widgets already on your desktop/panel will show as missing until you remove them.)"
else
    echo "Removed. (GNOME's search stops listing Logos after you next log in.)"
fi
