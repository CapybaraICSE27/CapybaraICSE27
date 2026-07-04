#!/usr/bin/env bash
# run-with-service.sh — Start a service, health-gate it, then exec the agent.
#
# This is the in-repo, npm-oriented service runner for JavaScript frontend
# evaluation targets. It supports services declared in the sibling services.json
# with build_system: "npm" (or any interpreter that can be invoked from the
# shell). It is NOT a drop-in for the gerbil external runner, which handles
# Maven/Gradle Java services.
#
# Usage:
#   run-with-service.sh <service-id> --repo <dir> --host <host> --port <port> -- <agent-cmd...>
#
# services.json must be in the same directory as this script. JSON is parsed
# with python3 (jq is not installed in the base image).
set -euo pipefail

# ---- Argument parsing ----

SERVICE_ID="${1:?Usage: $(basename "$0") <service-id> --repo <dir> --host <host> --port <port> -- <cmd...>}"
shift

REPO=""
HOST="127.0.0.1"
PORT=""
AGENT_CMD=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo)  REPO="${2:?--repo requires a value}";  shift 2 ;;
        --host)  HOST="${2:?--host requires a value}";  shift 2 ;;
        --port)  PORT="${2:?--port requires a value}";  shift 2 ;;
        --)      shift; AGENT_CMD=("$@"); break ;;
        *)       echo "[service] Unexpected argument: $1" >&2; exit 1 ;;
    esac
done

: "${REPO:?--repo is required}"
: "${PORT:?--port is required}"

if [[ ${#AGENT_CMD[@]} -eq 0 ]]; then
    echo "[service] No agent command provided after --" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICES_JSON="$SCRIPT_DIR/services.json"

if [[ ! -f "$SERVICES_JSON" ]]; then
    echo "[service] services.json not found: $SERVICES_JSON" >&2
    exit 1
fi

# ---- Parse service config via Python (jq not available in base image) ----

CONFIG_FILE="$(mktemp)"
trap 'rm -f "$CONFIG_FILE"' EXIT

python3 - "$SERVICE_ID" "$SERVICES_JSON" "$CONFIG_FILE" <<'PYEOF'
import json, shlex, sys

service_id, services_json, config_file = sys.argv[1], sys.argv[2], sys.argv[3]

with open(services_json) as f:
    data = json.load(f)

services = data.get("services", {})
if service_id not in services:
    known = ", ".join(services.keys()) or "(none)"
    sys.exit(f"[service] Unknown service '{service_id}'. Available: {known}")

svc = services[service_id]

base_path = svc.get("base_path", "/")

out = [
    "REPO_SUBDIR=" + shlex.quote(svc.get("repo_subdir", ".")),
    "RUN_CMD=" + shlex.quote(svc.get("run", "")),
    "BASE_PATH=" + shlex.quote(base_path),
    "HEALTH_PATH=" + shlex.quote(svc.get("health_path", base_path)),
    "HEALTH_TIMEOUT=" + str(int(svc.get("health_timeout_seconds", 120))),
]

builds = svc.get("build", [])
out.append("BUILD_COUNT=" + str(len(builds)))
for i, b in enumerate(builds):
    out.append(f"BUILD_{i}=" + shlex.quote(b))

env_dict = svc.get("env", {})
for k, v in env_dict.items():
    out.append(f"SVC_ENV_{k}=" + shlex.quote(str(v)))
out.append("SVC_ENV_KEYS=" + shlex.quote(" ".join(env_dict.keys())))

with open(config_file, "w") as f:
    f.write("\n".join(out) + "\n")
PYEOF

# shellcheck source=/dev/null
source "$CONFIG_FILE"

# ---- Export service-level environment variables ----

for k in $SVC_ENV_KEYS; do
    var="SVC_ENV_${k}"
    export "$k"="${!var}"
done

# ---- Build ----

SERVICE_DIR="$REPO/$REPO_SUBDIR"
cd "$SERVICE_DIR"

echo "[service] Building '$SERVICE_ID' in $SERVICE_DIR" >&2
for (( i=0; i<BUILD_COUNT; i++ )); do
    var="BUILD_${i}"
    BUILD_STEP="${!var}"
    echo "[service] Build step $((i+1))/$BUILD_COUNT: $BUILD_STEP" >&2
    eval "$BUILD_STEP"
done

# ---- Start ----

# Substitute the runtime ${PORT} placeholder in the run command.
RUN_EXPANDED="${RUN_CMD//\$\{PORT\}/$PORT}"

echo "[service] Starting '$SERVICE_ID': $RUN_EXPANDED" >&2
SERVICE_LOG="$(mktemp)"

eval "$RUN_EXPANDED" >"$SERVICE_LOG" 2>&1 &
SERVICE_PID=$!

# Update the EXIT trap to also kill the service and clean up the log.
trap 'kill "$SERVICE_PID" 2>/dev/null || true; rm -f "$SERVICE_LOG" "$CONFIG_FILE"' EXIT

# ---- Health-gate ----

HEALTH_URL="http://${HOST}:${PORT}${HEALTH_PATH}"
echo "[service] Waiting for $HEALTH_URL (timeout: ${HEALTH_TIMEOUT}s)" >&2

DEADLINE=$(( $(date +%s) + HEALTH_TIMEOUT ))
until curl -fsS --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; do
    if ! kill -0 "$SERVICE_PID" 2>/dev/null; then
        echo "[service] Service process exited unexpectedly. Last 20 log lines:" >&2
        tail -n 20 "$SERVICE_LOG" >&2
        exit 1
    fi
    if (( $(date +%s) >= DEADLINE )); then
        echo "[service] Health check timed out after ${HEALTH_TIMEOUT}s. Last 20 log lines:" >&2
        tail -n 20 "$SERVICE_LOG" >&2
        exit 1
    fi
    sleep 2
done

echo "[service] '$SERVICE_ID' is healthy at $HEALTH_URL" >&2

# ---- Export service URL for the agent and Playwright ----

export SERVICE_BASE_URL="http://${HOST}:${PORT}${BASE_PATH}"
# PLAYWRIGHT_BASE_URL is read by the prompt templates and can be referenced in
# playwright.config.ts as the baseURL. SERVICE_BASE_URL is the canonical name
# used across all workloads.
export PLAYWRIGHT_BASE_URL="$SERVICE_BASE_URL"
# Export PORT as a plain integer so playwright.config.ts files that read
# process.env.PORT to derive their baseURL get the correct value (e.g. zudoku).
export PORT

echo "[service] SERVICE_BASE_URL=$SERVICE_BASE_URL" >&2
echo "[service] Handing off to agent" >&2

exec "${AGENT_CMD[@]}"
