#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/../projects/zudoku"
DIST_DIR="$SCRIPT_DIR/../dist/zudoku"

echo "==> Deploying zudoku (pnpm + nx)"
cd "$PROJECT_DIR"

echo "  Installing dependencies..."
pnpm install --frozen-lockfile

echo "  Building core library packages (nx run-many, skipping example apps)..."
# Target only the library packages; example apps (many-apis, mermaid, etc.)
# have optional external dependencies not required for the library dist.
npx nx run-many -t=build --projects=zudoku,@zudoku/plugin-graphql,@zudoku/plugin-search-algolia,create-zudoku 2>&1 || \
    npx nx run zudoku:build  # fallback to just the main package

echo "  Copying dist artifacts to $DIST_DIR..."
mkdir -p "$DIST_DIR"
# Collect dist/ from each package under packages/
for pkg_dir in packages/*/; do
    pkg_name="$(basename "$pkg_dir")"
    if [ -d "${pkg_dir}dist" ]; then
        mkdir -p "$DIST_DIR/$pkg_name"
        cp -r "${pkg_dir}dist/." "$DIST_DIR/$pkg_name/"
    fi
done

echo "==> zudoku deploy complete: $DIST_DIR"
