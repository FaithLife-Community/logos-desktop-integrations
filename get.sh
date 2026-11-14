#!/bin/sh
# One-command install or update of Logos Plasma integrations from the latest release:
#   curl -fsSL https://raw.githubusercontent.com/FaithLife-Community/logos-plasma-integrations/main/get.sh | sh
# Downloads the release into a temporary folder, runs its install.sh, then removes the download.
# To install a particular version instead: ... | sh -s v0.1.0
set -eu
repo=FaithLife-Community/logos-plasma-integrations
tag=${1:-}
if [ -z "$tag" ]; then
    tag=$(curl -fsSL "https://api.github.com/repos/$repo/releases/latest" |
          sed -n 's/.*"tag_name": *"\([^"]*\)".*/\1/p' | head -n 1)
fi
[ -n "$tag" ] || { echo "Couldn't find the latest release of $repo" >&2; exit 1; }

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
echo "Downloading Logos Plasma integrations $tag"
curl -fsSL "https://github.com/$repo/archive/refs/tags/$tag.tar.gz" | tar -xz -C "$tmp" --strip-components=1
sh "$tmp/install.sh"
