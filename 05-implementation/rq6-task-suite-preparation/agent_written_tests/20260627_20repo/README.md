# RQ6 Agent-Written Test Source Files (20 Repos, 2026-06-27)

This directory contains the RQ6 agent-written test source files analyzed in the
20-repo artifact. It intentionally includes only generated test source files
plus manifests; it does not include cloned repositories, dependencies, browser
reports, logs, run directories, or review bundles.

## Provenance

- Source file manifest: `manifests/agent_final20_manifest.jsonl`
- Source extracted test cases: `combined_agent20/agent_written_tests/test_cases.jsonl`
- Source artifact provenance: `combined_agent20/COMBINED_PROVENANCE.json`
- Combined tests represented: 2054
- Repositories represented: 20
- Unique implementation files archived: 162

The files under `source_files/` come from the pinned subject-repo commits
recorded in the final file manifest. Each entry in `source_manifest.json`
records the original repo, commit, source path, archived path, byte size, SHA-256
digest, and number of extracted tests from that file.

## Repo Summary

| Repo | Extracted tests | Files | Pinned commit |
|---|---:|---:|---|
| HemmeligOrg/Hemmelig.app | 154 | 7 | `629b2ec971027184f1685c7b7aea95c1dfab5f43` |
| TriliumNext/Trilium | 68 | 7 | `fe94c296ae6ce596d0f7634077a151cdac3d005d` |
| actualbudget/actual | 126 | 11 | `2683a36ab810e74fc8787c7ef4c55889d0045df6` |
| altair-graphql/altair | 101 | 15 | `1dff3a1014bed38d608f05ec11ec73d84b4ac957` |
| cypress-io/cypress-realworld-app | 84 | 9 | `632e01a0cced4e1779992c800293c96abd13ce4c` |
| epicweb-dev/epic-stack | 104 | 6 | `0c3060abe3ac261e95a49124f59fe14dbb0d6e80` |
| git-truck/git-truck | 60 | 3 | `bfb2024611f50582084f5fa2ddd68c77bd602409` |
| gridstack/gridstack.js | 154 | 8 | `b2af38b4cf3e0b2040520007fa90f05229970664` |
| keystonejs/keystone | 47 | 6 | `fbab4436a9ac71e332318ae35854c2eea9ac8e68` |
| laststance/react-typescript-todomvc-2022 | 33 | 1 | `116dd1f51bc7fe206958401c3251d43bcc051e52` |
| letterpad/letterpad | 128 | 14 | `5639e09b738f9c90ca877cd4a7c95f562e1bdc62` |
| maplibre/maputnik | 121 | 9 | `c0f938cacb29c2b56f06d20d8375c4351f53d200` |
| marmelab/react-admin | 68 | 7 | `6f79ddb5eacfac65170edceb52703862cdce40d0` |
| mermaid-js/mermaid | 122 | 7 | `969521aed9ae4f3c54a959ce27f85b2283c4e92f` |
| motiondivision/motion-vue | 109 | 8 | `509fc3287287b728625688989047ec6636fe7130` |
| openplayerjs/openplayerjs | 126 | 7 | `359f196bb83022b596b99dd31212ef3905193afb` |
| super-productivity/super-productivity | 142 | 11 | `76a21c9d19efbb30003c3ecb87c77c0f87569999` |
| swup/swup | 119 | 17 | `958c59726fc2dd377ad20eada488f857f8d0fd23` |
| tldraw/tldraw | 70 | 3 | `26f673ed8c713fa3068149a5bd9d4ffe05941476` |
| zuplo/zudoku | 118 | 6 | `578d1e4ae0a93645b7c9a66c8c5f0b813f5a62ce` |

## Layout

- `source_files/<owner>__<repo>/<original file path>`: archived implementation source files.
- `agent_final20_file_manifest.jsonl`: copied final file manifest used to identify the source files.
- `source_manifest.json`: compact provenance and checksums for these tracked source files.
