# RQ6 Agent-Generated UI Test Artifacts

This directory contains the benchmark, harness, prompts, and generated-test
source files used for RQ6.

## RQ6 Process

- Claude Code explored deployed applications through the harness in
  `harness/general-agent-eval/` and generated Playwright specs under
  `rq6-agent/` directories.

## RQ6 Repositories

| Repository | Upstream URL | Application Category |
|---|---|---|
| `actualbudget/actual` | [github.com/actualbudget/actual](https://github.com/actualbudget/actual) | personal finance / budgeting app |
| `altair-graphql/altair` | [github.com/altair-graphql/altair](https://github.com/altair-graphql/altair) | GraphQL API client |
| `cypress-io/cypress-realworld-app` | [github.com/cypress-io/cypress-realworld-app](https://github.com/cypress-io/cypress-realworld-app) | banking / payments demo app |
| `epicweb-dev/epic-stack` | [github.com/epicweb-dev/epic-stack](https://github.com/epicweb-dev/epic-stack) | full-stack web app template |
| `git-truck/git-truck` | [github.com/git-truck/git-truck](https://github.com/git-truck/git-truck) | repository visualization tool |
| `gridstack/gridstack.js` | [github.com/gridstack/gridstack.js](https://github.com/gridstack/gridstack.js) | layout/grid UI library |
| `HemmeligOrg/Hemmelig.app` | [github.com/HemmeligOrg/Hemmelig.app](https://github.com/HemmeligOrg/Hemmelig.app) | secret-sharing app |
| `keystonejs/keystone` | [github.com/keystonejs/keystone](https://github.com/keystonejs/keystone) | CMS/admin platform |
| `laststance/react-typescript-todomvc-2022` | [github.com/laststance/react-typescript-todomvc-2022](https://github.com/laststance/react-typescript-todomvc-2022) | todo app demo |
| `letterpad/letterpad` | [github.com/letterpad/letterpad](https://github.com/letterpad/letterpad) | blogging/CMS platform |
| `maplibre/maputnik` | [github.com/maplibre/maputnik](https://github.com/maplibre/maputnik) | map style editor |
| `marmelab/react-admin` | [github.com/marmelab/react-admin](https://github.com/marmelab/react-admin) | admin dashboard framework/demo |
| `mermaid-js/mermaid` | [github.com/mermaid-js/mermaid](https://github.com/mermaid-js/mermaid) | diagramming renderer/playground |
| `motiondivision/motion-vue` | [github.com/motiondivision/motion-vue](https://github.com/motiondivision/motion-vue) | animation UI library |
| `openplayerjs/openplayerjs` | [github.com/openplayerjs/openplayerjs](https://github.com/openplayerjs/openplayerjs) | media player UI library |
| `super-productivity/super-productivity` | [github.com/super-productivity/super-productivity](https://github.com/super-productivity/super-productivity) | task/project management app |
| `swup/swup` | [github.com/swup/swup](https://github.com/swup/swup) | page-transition/navigation library |
| `tldraw/tldraw` | [github.com/tldraw/tldraw](https://github.com/tldraw/tldraw) | drawing/whiteboard app |
| `TriliumNext/Trilium` | [github.com/TriliumNext/Trilium](https://github.com/TriliumNext/Trilium) | note-taking/knowledge-base app |
| `zuplo/zudoku` | [github.com/zuplo/zudoku](https://github.com/zuplo/zudoku) | API documentation portal |

## Contents

- `benchmark/capybara-benchmark/`: 20-project RQ6 benchmark wrapper, submodule manifest, deploy scripts, and `manifest.jsonl` for generated tests.
- `harness/general-agent-eval/`: general agent execution harness, Docker runner, service runner, and UI-test-generation prompts.
- `agent-written-tests/`: archived source files for the final 20-repo agent-written tests analyzed by the RQ1-RQ5 pipeline.
- `rq6_repositories.csv` and `rq6_repositories.json`: the 20 RQ6 repositories, upstream URLs, application categories, and generated-test counts.

