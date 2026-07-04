#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/../projects/swup"
DIST_DIR="$SCRIPT_DIR/../dist/swup"

echo "==> Deploying swup (npm)"
cd "$PROJECT_DIR"

echo "  Installing dependencies..."
npm ci

echo "  Building..."
npm run build

echo "  Copying dist artifacts to $DIST_DIR..."
mkdir -p "$DIST_DIR"
cp -r dist/. "$DIST_DIR/"

echo "  Instrumenting dist into tests/fixtures/dist/ for demo server..."
npm run test:e2e:instrument

echo "==> swup deploy complete: $DIST_DIR"
