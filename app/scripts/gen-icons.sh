#!/usr/bin/env bash
# Rasterize the PWA icon set from the SVG sources. No binaries live in git;
# this runs in CI (docs.yml) and can be run locally to preview real icons.
# Requires rsvg-convert  (Debian/Ubuntu: apt install librsvg2-bin · macOS: brew install librsvg)
set -euo pipefail

cd "$(dirname "$0")/.."            # -> app/
out="assets/icons"
mkdir -p "$out"

if ! command -v rsvg-convert >/dev/null 2>&1; then
  echo "error: rsvg-convert not found. Install librsvg (apt install librsvg2-bin / brew install librsvg)." >&2
  exit 1
fi

render() { rsvg-convert -w "$2" -h "$2" "$1" -o "$3"; }

# 'any' icons — rounded badge, fuller art
render assets/icon.svg       192 "$out/icon-192.png"
render assets/icon.svg       512 "$out/icon-512.png"
# 'maskable' icons — opaque, art inside the 80% safe zone
render assets/icon-solid.svg 192 "$out/icon-192-maskable.png"
render assets/icon-solid.svg 512 "$out/icon-512-maskable.png"
# iOS — opaque, no transparency (iOS applies its own rounding)
render assets/icon-solid.svg 180 "$out/apple-touch-icon.png"

echo "PWA icons generated -> app/$out/"
