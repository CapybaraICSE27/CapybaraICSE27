#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/../projects/openplayerjs"
DIST_DIR="$SCRIPT_DIR/../dist/openplayerjs"

echo "==> Deploying openplayerjs (pnpm)"
cd "$PROJECT_DIR"

# Project requires Node 26.3.1 / pnpm 10.32.1; patch files for local deployment.
PKG_BACKUP="$(cat package.json)"
WS_BACKUP="$(cat pnpm-workspace.yaml)"
trap '
    printf "%s" "$PKG_BACKUP" > package.json
    printf "%s" "$WS_BACKUP"  > pnpm-workspace.yaml
' EXIT

PNPM_VER="$(pnpm --version)"

# Remove strict engine requirement; update packageManager to installed pnpm version.
node -e "
const fs = require('fs');
const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));
delete pkg.engines;
pkg.packageManager = 'pnpm@' + process.argv[1];
fs.writeFileSync('package.json', JSON.stringify(pkg, null, 2));
" -- "$PNPM_VER"

# Disable engineStrict and approve the required build script in workspace config.
node -e "
const fs = require('fs');
let ws = fs.readFileSync('pnpm-workspace.yaml', 'utf8');
ws = ws.replace(/engineStrict:\s*true/, 'engineStrict: false');
ws = ws.replace(/unrs-resolver:\s*set this to true or false/, 'unrs-resolver: true');
fs.writeFileSync('pnpm-workspace.yaml', ws);
"

echo "  Installing dependencies..."
CI=true pnpm install --no-frozen-lockfile

echo "  Building..."
pnpm run build

echo "  Copying dist artifacts to $DIST_DIR..."
mkdir -p "$DIST_DIR"
# openplayerjs is a monorepo; each package emits dist/ under packages/<name>/dist/
for pkg_dir in packages/*/; do
    pkg_name="$(basename "$pkg_dir")"
    if [ -d "${pkg_dir}dist" ]; then
        mkdir -p "$DIST_DIR/$pkg_name"
        cp -r "${pkg_dir}dist/." "$DIST_DIR/$pkg_name/"
    fi
done

echo "==> openplayerjs deploy complete: $DIST_DIR"
