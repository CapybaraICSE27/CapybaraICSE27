# syntax=docker/dockerfile:1.7
#
# JavaScript workload layer: Node.js 20 LTS and the OS-level browser
# dependencies that Playwright requires to run Chromium/Firefox/WebKit in
# headless mode. This is the workload layer for JavaScript frontend evaluation
# targets and is independent of the selected agent -- it builds
# `FROM ${BASE_IMAGE}`, which the orchestrator points at an agent layer.
#
# Playwright browser *binaries* are NOT pre-installed here. They are downloaded
# at test-run time via `npx playwright install <browser>`, which lets each
# project pin its own Playwright version. OS-level browser dependencies ARE
# pre-installed (as root) so the non-root agent user can run browsers without
# needing `--with-deps` at runtime. PLAYWRIGHT_BROWSERS_PATH is set to a path
# inside the agent's home dir so downloaded binaries are writable.

ARG BASE_IMAGE=general-agent-eval-base:latest
FROM ${BASE_IMAGE}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

USER root

# Node.js 20 LTS via the official NodeSource signed apt repository.
# Mirrors the adoptium keyring pattern used by Dockerfile.java.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
        | gpg --dearmor -o /usr/share/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodist main" \
        > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Pre-install Playwright browser OS dependencies so the non-root agent user
# can run browsers without --with-deps at test time. A temporary global
# Playwright install drives `playwright install-deps`; it is removed afterwards
# since projects supply their own pinned version via npm ci.
RUN npm install -g playwright --no-fund --no-audit \
    && playwright install-deps \
    && npm uninstall -g playwright \
    && rm -rf /var/lib/apt/lists/*

# Enable pnpm and yarn via corepack (bundled with Node 20) so projects that
# use those package managers work without a separate global install.
RUN corepack enable

# Point Playwright's browser cache at the agent user's home directory so that
# `npx playwright install <browser>` writes to a writable path at runtime.
# Suppress npm funding/audit noise during npm ci runs inside the container.
ENV PLAYWRIGHT_BROWSERS_PATH=/home/agent/.cache/ms-playwright \
    npm_config_fund=false \
    npm_config_audit=false

USER agent
