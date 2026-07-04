#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PROJECTS=(
    "swup"
    "openplayerjs"
    "motion_vue"
    "zudoku"
    "gridstack"
)

FAILED=()

run_deploy() {
    local name="$1"
    local script="$SCRIPT_DIR/deploy_${name}.sh"
    local dest
    dest="$(cd "$SCRIPT_DIR/.." && pwd)/dist/$name"
    if bash "$script"; then
        local count
        count=$(find "$dest" -type f 2>/dev/null | wc -l | tr -d ' ')
        echo "[OK] $name  →  $dest  ($count files)"
    else
        echo "[FAIL] $name"
        FAILED+=("$name")
    fi
}

for proj in "${PROJECTS[@]}"; do
    run_deploy "$proj"
done

if [ ${#FAILED[@]} -gt 0 ]; then
    echo ""
    echo "Failed projects: ${FAILED[*]}"
    exit 1
fi

echo ""
echo "All projects deployed successfully."
