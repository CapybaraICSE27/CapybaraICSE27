#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/../projects/motion-vue"
DIST_DIR="$SCRIPT_DIR/../dist/motion-vue"

echo "==> Deploying motion-vue (pnpm)"
cd "$PROJECT_DIR"

echo "  Installing dependencies..."
pnpm install --frozen-lockfile

echo "  Building..."
pnpm run build

echo "  Copying dist artifacts to $DIST_DIR..."
mkdir -p "$DIST_DIR"
# motion-vue uses a monorepo; collect all package dist outputs
find . -path "*/node_modules" -prune -o -type d -name "dist" -print | while read -r d; do
    rel="${d#./}"
    pkg_name="$(basename "$(dirname "$d")")"
    mkdir -p "$DIST_DIR/$pkg_name"
    cp -r "$d/." "$DIST_DIR/$pkg_name/"
done

echo "==> motion-vue deploy complete: $DIST_DIR"
