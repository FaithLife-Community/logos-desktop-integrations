#!/bin/sh
# Remove Logos Plasma integrations. Leaves ~/.config/logos-plasma alone.
data=${XDG_DATA_HOME:-$HOME/.local/share}
kwriteconfig6 --file krunnerrc --group Plugins --key logos-plasmaEnabled --notify false
pkill -f "$data/logos-plasma/logos_plasma.py" 2>/dev/null
rm -f "$data/krunner/dbusplugins/logos-plasma.desktop" \
      "$data/dbus-1/services/io.github.FaithlifeCommunity.LogosPlasma.service" \
      "$data"/icons/hicolor/256x256/apps/logos-plasma.*
rm -rf "$data/logos-plasma"
systemctl --user disable --now logos-plasma-reminders.timer >/dev/null 2>&1
rm -f "${XDG_CONFIG_HOME:-$HOME/.config}"/systemd/user/logos-plasma-reminders.* \
      "$data/applications/logos-plasma-lookup.desktop" "$data/applications/logos-plasma.desktop"
kwriteconfig6 --file kglobalshortcutsrc --group services --group logos-plasma-lookup.desktop --key _launch --delete
kbuildsycoca6 >/dev/null 2>&1
kwriteconfig6 --file krunnerrc --group Plugins --key logos-plasmaEnabled --delete
for id in io.github.FaithlifeCommunity.LogosVerseOfTheDay io.github.FaithlifeCommunity.LogosReadingPlans io.github.FaithlifeCommunity.LogosShowcase; do
    kpackagetool6 -t Plasma/Applet --remove "$id" >/dev/null 2>&1
done
echo "Removed. (Widgets already on your desktop/panel will show as missing until you remove them.)"
