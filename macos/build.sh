#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
variant=local-data
conditions='LOGOS_LOCAL_DATA'
if [ "${1:-}" = --without-local-data ]; then
    variant=commands-only
    conditions=''
    shift
fi
if ! command -v xcodegen >/dev/null; then
    echo 'Install XcodeGen first: brew install xcodegen' >&2
    exit 1
fi
xcodegen generate
xcodebuild -project LogosDesktopIntegrations.xcodeproj -scheme LogosDesktopIntegrations \
    -configuration Release -derivedDataPath "build/$variant" \
    "SWIFT_ACTIVE_COMPILATION_CONDITIONS=$conditions" "$@" build
printf '\nBuilt: %s/build/%s/Build/Products/Release/LogosDesktopIntegrations.app\n' "$PWD" "$variant"
