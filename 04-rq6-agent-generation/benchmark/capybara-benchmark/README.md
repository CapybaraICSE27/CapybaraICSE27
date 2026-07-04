# capybara-benchmark

A benchmark harness that builds and deploys five open-source JavaScript projects as git submodules. Each project is installed, compiled, and its distribution artifacts copied into a local `dist/` directory.

---

## Prerequisites

### System tools

| Tool | Minimum version | Purpose |
|---|---|---|
| **Git** | 2.20+ | Cloning submodules |
| **Node.js** | 25.x | Building all JS projects |
| **npm** | 10+ | Bundled with Node.js; used by swup |
| **pnpm** | 11.x | Used by openplayerjs, motion-vue, zudoku |
| **yarn** | 1.22+ | Used by gridstack |
| **Python** | 3.11+ | Running `deploy.py` orchestrator |
| **uv** | 0.9+ | Python environment management |

Install pnpm and yarn via npm if not already present:

```bash
npm install -g pnpm yarn
```

Install uv:

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Per-project tooling

| Project | Build system | Notes |
|---|---|---|
| swup | microbundle | Installed automatically via `npm ci` |
| openplayerjs | turbo + rollup | Installed automatically via `pnpm install` |
| motion-vue | vite + unbuild | Installed automatically via `pnpm install` |
| zudoku | nx + tsdown | Installed automatically via `pnpm install` |
| gridstack | grunt + webpack | Installed automatically via `yarn install` |

---

## Getting started

### 1. Clone with submodules

```bash
git clone --recurse-submodules <repo-url>
# Or, if already cloned without submodules:
git submodule update --init --recursive
```

### 2. Set up the Python environment

```bash
uv sync
```

This creates `.venv/` and installs `pytest` and `ruff` as dev dependencies.

---

## Deploying projects

### Deploy all five projects

```bash
# Using the Python orchestrator (recommended):
uv run deploy

# Using the shell script directly:
bash scripts/deploy_all.sh
```

### Deploy a single project

```bash
# Python orchestrator:
uv run deploy swup
uv run deploy openplayerjs
uv run deploy motion-vue
uv run deploy zudoku
uv run deploy gridstack

# Shell scripts directly:
bash scripts/deploy_swup.sh
bash scripts/deploy_openplayerjs.sh
bash scripts/deploy_motion_vue.sh
bash scripts/deploy_zudoku.sh
bash scripts/deploy_gridstack.sh
```

### Deploy multiple specific projects

```bash
uv run deploy swup gridstack
```

---

## Where artifacts are deployed

All build artifacts land under `dist/` at the root of this repository:

```
dist/
├── swup/                    # CJS, ESM, UMD bundles + type declarations
│   ├── Swup.cjs
│   ├── Swup.modern.js
│   ├── Swup.module.js
│   ├── Swup.umd.js
│   └── types/
│
├── openplayerjs/            # Five sub-packages (monorepo)
│   ├── core/
│   ├── player/              # openplayer.js UMD bundle + CSS
│   ├── hls/
│   ├── ads/
│   └── youtube/
│
├── motion-vue/              # Vue animation library
│   └── motion/              # ESM bundles + type declarations
│
├── zudoku/                  # API documentation framework (four packages)
│   ├── zudoku/              # Core library
│   ├── plugin-graphql/
│   ├── plugin-search-algolia/
│   └── create-zudoku/       # CLI scaffolding tool
│
└── gridstack/               # Grid layout library
    ├── gridstack-all.js      # Full UMD bundle (all-in-one)
    ├── gridstack.js          # Core UMD module
    ├── gridstack.css         # Default theme
    ├── gridstack.min.css
    └── *.d.ts                # type declarations
```

### Artifact counts (after a full deploy)

| Project | Files | Dist path |
|---|---|---|
| swup | 62 | `dist/swup/` |
| openplayerjs | 144 | `dist/openplayerjs/` |
| motion-vue | 215 | `dist/motion-vue/` |
| zudoku | 61 | `dist/zudoku/` |
| gridstack | 50 | `dist/gridstack/` |

---

## Opening in the browser

Three projects ship actual runnable apps; two are library-only.

### Start all servers

```bash
bash serve.sh
```

This starts six servers and prints their URLs. Press `Ctrl+C` to stop everything.

> **swup** and **openplayerjs** must be built before serving — run their deploy scripts first (see [Deploying projects](#deploying-projects) above).

### What opens where

| URL | Project | What it is |
|---|---|---|
| `http://localhost:8274/` | **swup** | Test-fixture pages demonstrating page transitions (page-1 through page-3, animations, caching, etc.) |
| `http://localhost:4173/examples/basic.html` | **openplayerjs** | HTML5 media player examples — basic, HLS, ads, captions, YouTube, and more |
| `http://localhost:3001/demo/` | **gridstack** | Full interactive demo collection — drag, resize, nested grids, responsive layouts (20+ demos) |
| `http://localhost:3002` | **zudoku** (cosmo-cargo) | Complete API docs site — Cosmo Cargo shipping API with auth, OpenAPI explorer, GraphQL |
| `http://localhost:3003` | **zudoku** (with-vite-config) | Minimal zudoku setup showing OpenAPI docs with Vite config |
| `http://localhost:3004` | **motion-vue** | Live Vite playground — Vue 3 animation components (`<Motion>`, directives, spring physics) |

### Individual servers

```bash
# swup — must run from the project root; serve.json sets public dir to tests/fixtures/
# Requires: bash scripts/deploy_swup.sh first
cd projects/swup && npx serve -n -S -L -p 8274 --config ./tests/config/serve.json

# openplayerjs — serves repo root so /packages/*/dist/ import maps resolve
# Requires: bash scripts/deploy_openplayerjs.sh first
npx serve -l 4173 projects/openplayerjs

# gridstack — must be served from the project root so demo/ can reach ../dist/
npx serve -l 3001 projects/gridstack

# zudoku cosmo-cargo (pre-built static site)
npx serve -l 3002 projects/zudoku/examples/cosmo-cargo/dist

# zudoku with-vite-config (pre-built static site)
npx serve -l 3003 projects/zudoku/examples/with-vite-config/dist

# motion-vue playground (Vite dev server — compiles on the fly)
cd projects/motion-vue && pnpm --filter @motion-vue/playground-vite dev --port 3004
```

---

## Repository layout

```
capybara-benchmark/
├── projects/                # Git submodules (source)
│   ├── swup/
│   ├── openplayerjs/
│   ├── motion-vue/
│   ├── zudoku/
│   └── gridstack/
├── scripts/                 # Per-project deploy shell scripts
│   ├── deploy_swup.sh
│   ├── deploy_openplayerjs.sh
│   ├── deploy_motion_vue.sh
│   ├── deploy_zudoku.sh
│   ├── deploy_gridstack.sh
│   └── deploy_all.sh        # Runs all five in sequence
├── dist/                    # Build artifacts (git-ignored)
├── deploy.py                # Python orchestrator (uv run deploy)
├── serve.sh                 # Starts local servers for all runnable apps
└── pyproject.toml           # Python project + dev dependencies
```

---

## Notes

- `dist/` is not committed to git — re-run the deploy scripts after a fresh clone.
- **openplayerjs** requires Node 26.3.1 per its `engines` field; the deploy script patches this constraint at install time so it builds on Node 25.x.
- **gridstack** build covers the core JS/CSS and type-declaration output only (grunt + webpack + tsc). The Angular and React wrapper packages require `@angular/cli` / additional tooling and are skipped in the default build.
- **zudoku** builds the four core library packages (`zudoku`, `plugin-graphql`, `plugin-search-algolia`, `create-zudoku`).
