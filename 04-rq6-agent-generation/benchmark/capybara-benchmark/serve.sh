#!/usr/bin/env bash
# Start local servers for every project that ships a runnable app.
#
# Projects with a browser app:
#   gridstack    → http://localhost:3001/demo/
#   zudoku       → http://localhost:3002  (cosmo-cargo API docs)
#   zudoku       → http://localhost:3003  (with-vite-config example)
#   motion-vue   → http://localhost:3004  (Vite playground)
#
# Library-only (no app to serve):
#   swup         — page-transition library; embed into your own HTML/site
#   openplayerjs — HTML5 media player library; embed into your own HTML/site
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDS=()

cleanup() {
    echo ""
    echo "Stopping all servers..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
}
trap cleanup EXIT INT TERM

# ── swup (page-transition library — test fixtures as demo) ────────────────
# Requires: bash scripts/deploy_swup.sh first (builds + instruments dist into
# tests/fixtures/dist/ so the HTML pages can load /dist/Swup.umd.js).
echo "[swup]        http://localhost:8274/  (page-transition fixtures)"
cd "$ROOT/projects/swup"
npx --yes serve -n -S -L -p 8274 --config ./tests/config/serve.json --no-clipboard &
PIDS+=($!)
cd "$ROOT"

# ── openplayerjs (HTML5 media player — example HTML pages) ────────────────
# Requires: bash scripts/deploy_openplayerjs.sh first (builds packages in
# packages/*/dist/ so the import maps in examples/*.html resolve correctly).
echo "[openplayerjs] http://localhost:4173/examples/basic.html  (player demos)"
npx --yes serve -l 4173 "$ROOT/projects/openplayerjs" --no-clipboard &
PIDS+=($!)

# ── gridstack ──────────────────────────────────────────────────────────────
# Served from the project root because demo/ references ../dist/gridstack-all.js.
echo "[gridstack]  http://localhost:3001/demo/"
npx --yes serve -l 3001 "$ROOT/projects/gridstack" --no-clipboard &
PIDS+=($!)

# ── zudoku: cosmo-cargo example (rich API docs demo) ──────────────────────
# Pre-built static site — no compilation needed.
echo "[zudoku]     http://localhost:3002  (cosmo-cargo API docs)"
npx --yes serve -l 3002 "$ROOT/projects/zudoku/examples/cosmo-cargo/dist" --no-clipboard &
PIDS+=($!)

# ── zudoku: with-vite-config example (minimal docs setup) ─────────────────
# Pre-built static site — no compilation needed.
echo "[zudoku]     http://localhost:3003  (with-vite-config example)"
npx --yes serve -l 3003 "$ROOT/projects/zudoku/examples/with-vite-config/dist" --no-clipboard &
PIDS+=($!)

# ── motion-vue playground (Vite dev server, compiles on the fly) ──────────
# Not a pre-built static site — Vite compiles TypeScript/Vue on first request.
echo "[motion-vue] http://localhost:3004  (Vite playground — may take a moment)"
cd "$ROOT/projects/motion-vue"
pnpm --filter @motion-vue/playground-vite dev --port 3004 &
PIDS+=($!)
cd "$ROOT"

echo ""
echo "──────────────────────────────────────────────────────"
echo " swup fixtures       →  http://localhost:8274/"
echo " openplayerjs demos  →  http://localhost:4173/examples/basic.html"
echo " gridstack demo      →  http://localhost:3001/demo/"
echo " zudoku cosmo-cargo  →  http://localhost:3002"
echo " zudoku vite-config  →  http://localhost:3003"
echo " motion-vue play     →  http://localhost:3004"
echo "──────────────────────────────────────────────────────"
echo " Press Ctrl+C to stop all servers"
echo ""

wait
