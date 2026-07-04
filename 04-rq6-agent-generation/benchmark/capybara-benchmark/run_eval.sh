#!/usr/bin/env bash
# Run the Playwright test-generation agent against all 4 remaining capybara projects in parallel.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HARNESS="${HARNESS_DIR:-$ROOT/../harness/general-agent-eval}"
LOGS="$ROOT/eval-logs"
mkdir -p "$LOGS"

# ── Start missing services ────────────────────────────────────────────────────

echo "[services] Starting motion-vue on :5173..."
cd "$ROOT/projects/motion-vue"
pnpm --filter @motion-vue/playground-vite dev --port 5173 --host 127.0.0.1 >"$LOGS/motion-vue-server.log" 2>&1 &
MVPID=$!
cd "$ROOT"

echo "[services] Killing any leftover process on :4321..."
lsof -ti:4321 | xargs kill -9 2>/dev/null || true
sleep 1

echo "[services] Starting zudoku on :4321 (dev mode)..."
cd "$ROOT/projects/zudoku"
PORT=4321 pnpm --filter cosmo-cargo exec zudoku dev --port 4321 >"$LOGS/zudoku-server.log" 2>&1 &
ZDPID=$!
cd "$ROOT"

# ── Health-gate the two new services ─────────────────────────────────────────

wait_for() {
  local url="$1" name="$2" timeout="${3:-60}"
  local deadline=$(( $(date +%s) + timeout ))
  echo "[services] Waiting for $name at $url..."
  until curl -fsS --max-time 3 "$url" >/dev/null 2>&1; do
    if (( $(date +%s) >= deadline )); then
      echo "[ERROR] $name did not start in ${timeout}s. Check $LOGS/${name}-server.log" >&2
      exit 1
    fi
    sleep 2
  done
  echo "[services] $name is ready."
}

wait_for "http://localhost:5173" "motion-vue" 120
wait_for "http://localhost:4321" "zudoku" 120

# ── Back up existing test files ───────────────────────────────────────────────

echo "[prep] Backing up existing test files..."

# swup: only backup tests/functional/ (tests/config + tests/fixtures must stay)
for f in "$ROOT/projects/swup/tests/functional/"*.spec.ts "$ROOT/projects/swup/tests/functional/plugins/"*.spec.ts; do
  [[ -f "$f" ]] && mv "$f" "${f}.bak" && echo "  backed up $f"
done

# openplayerjs
for f in "$ROOT/projects/openplayerjs/e2e/"*.spec.ts; do
  [[ -f "$f" ]] && mv "$f" "${f}.bak" && echo "  backed up $f"
done

# motion-vue
for f in "$ROOT/projects/motion-vue/tests/"*.spec.ts; do
  [[ -f "$f" ]] && mv "$f" "${f}.bak" && echo "  backed up $f"
done

# zudoku
for f in "$ROOT/projects/zudoku/e2e/"*.spec.ts; do
  [[ -f "$f" ]] && mv "$f" "${f}.bak" && echo "  backed up $f"
done

# ── Install Playwright chromium if not cached ─────────────────────────────────

if [[ ! -d "$HOME/.cache/ms-playwright" ]] || [[ -z "$(ls -A "$HOME/.cache/ms-playwright" 2>/dev/null)" ]]; then
  echo "[prep] Installing Playwright chromium (one-time)..."
  cd "$ROOT/projects/gridstack" && npx playwright install chromium
  cd "$ROOT"
fi

# ── Launch agents in parallel ─────────────────────────────────────────────────

run_agent() {
  local project="$1" url="$2" extra_env="${3:-}"
  echo "[agent] Starting $project → $url  (log: $LOGS/${project}-agent.log)"
  cd "$HARNESS"
  local env_flags=()
  [[ -n "$extra_env" ]] && env_flags=(--env "$extra_env")
  uv run general-agent-eval-claude-code \
    --input-dir "$ROOT/projects/$project" \
    --workload javascript \
    --prompt-var "service_base_url=$url" \
    --model claude-sonnet-4-6 \
    "${env_flags[@]}" \
    >"$LOGS/${project}-agent.log" 2>&1
  echo "[agent] $project DONE (exit $?)"
}

run_agent "swup"         "http://localhost:8274"  &
run_agent "openplayerjs" "http://localhost:4173"  &
run_agent "motion-vue"   "http://localhost:5173"  &
run_agent "zudoku"       "http://localhost:4321" "PORT=4321"  &

echo ""
echo "══════════════════════════════════════════════════════"
echo " 4 agents running in parallel. Tail logs with:"
echo "   tail -f $LOGS/swup-agent.log"
echo "   tail -f $LOGS/openplayerjs-agent.log"
echo "   tail -f $LOGS/motion-vue-agent.log"
echo "   tail -f $LOGS/zudoku-agent.log"
echo " Or watch all at once:"
echo "   tail -f $LOGS/*-agent.log"
echo "══════════════════════════════════════════════════════"

wait
echo ""
echo "[done] All agents finished. Stopping motion-vue and zudoku servers..."
kill "$MVPID" "$ZDPID" 2>/dev/null || true
echo "[done] Eval logs are in $LOGS/"
