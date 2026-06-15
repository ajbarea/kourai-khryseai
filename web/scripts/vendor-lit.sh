#!/usr/bin/env bash
# Vendor lit as self-contained, offline ESM under web/vendor/lit/.
#
# Unlike the PWA icons (CI-generated, not committed), the vendored lit files ARE
# committed: they are the offline runtime artifact so the web GUI never fetches
# lit from a CDN. Re-run this ONLY when bumping LIT_VERSION, then commit the
# regenerated web/vendor/lit/.
#
# esbuild code-splitting keeps ONE shared copy of lit-html across the core entry
# and the directive subpath. Bundling them separately would duplicate lit-html
# and break directives like repeat() (the brand/part machinery must be shared).
#
# Requires Node/npm; uses npx, so no permanent dependency is added to the repo.
set -euo pipefail

LIT_VERSION="3.2.1"
ESBUILD_VERSION="0.28.1"

cd "$(dirname "$0")/.."            # -> web/
out="vendor/lit"

if ! command -v npm >/dev/null 2>&1 || ! command -v npx >/dev/null 2>&1; then
  echo "error: npm/npx not found. Install Node.js (https://nodejs.org)." >&2
  exit 1
fi

stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT

echo "==> staging lit@$LIT_VERSION"
( cd "$stage" && npm init -y >/dev/null && npm install --no-audit --no-fund "lit@$LIT_VERSION" >/dev/null )

echo "==> esbuild@$ESBUILD_VERSION split-bundle -> web/$out"
rm -rf "$out"
npx --yes "esbuild@$ESBUILD_VERSION" \
  "index=$stage/node_modules/lit/index.js" \
  "directives/repeat=$stage/node_modules/lit/directives/repeat.js" \
  --bundle --splitting --format=esm --minify --target=es2022 \
  --outdir="$out" >/dev/null

echo "vendored lit -> web/$out/ :"
find "$out" -type f | sort
echo
echo "Added/removed a lit subpath import? Add it as an esbuild entry above, keep the"
echo "import map in web/index.html in sync, re-run, and commit web/$out/."
