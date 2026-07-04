#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/../projects/gridstack"
DIST_DIR="$SCRIPT_DIR/../dist/gridstack"

echo "==> Deploying gridstack.js (yarn)"
cd "$PROJECT_DIR"

echo "  Installing dependencies..."
# enable yarn via corepack if available, else fall back to npx
if command -v corepack &>/dev/null; then
    corepack enable yarn
fi
yarn install --frozen-lockfile

echo "  Building (core: grunt + webpack + tsc, skipping Angular/React wrappers)..."
# Run only the core build targets to avoid requiring ng/react CLI tools
npx grunt
npx webpack
npx tsc --project tsconfig.build.json --stripInternal

echo "  Copying dist artifacts to $DIST_DIR..."
mkdir -p "$DIST_DIR"
cp -r dist/. "$DIST_DIR/"

echo "==> gridstack deploy complete: $DIST_DIR"
