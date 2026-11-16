#!/bin/sh
# One-command install or update of the Logos desktop integrations (KDE Plasma or GNOME) from the latest release:
#   curl -fsSL https://raw.githubusercontent.com/FaithLife-Community/logos-desktop-integrations/main/get.sh | sh
# Downloads the release into a temporary folder, runs its install.sh, then removes the download.
# To install a particular version instead: ... | sh -s v0.5.0  (add --plasma or --gnome to choose the desktop)
set -eu
repo=FaithLife-Community/logos-desktop-integrations
tag= desk=
for a in "$@"; do
    case "$a" in --*) desk=$a ;; *) tag=$a ;; esac
done
if [ -z "$tag" ]; then
    tag=$(curl -fsSL "https://api.github.com/repos/$repo/releases/latest" |
          sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -n 1)
fi
[ -n "$tag" ] || { echo "Couldn't find the latest release of $repo" >&2; exit 1; }

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
echo "Downloading the Logos desktop integrations $tag"
curl -fsSL "https://github.com/$repo/archive/refs/tags/$tag.tar.gz" | tar -xz -C "$tmp" --strip-components=1
sh "$tmp/install.sh" $desk
