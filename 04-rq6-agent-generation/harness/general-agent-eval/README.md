# general-agent-eval

Harnesses for evaluating general coding agents against isolated repositories.

## Layout

- `src/general_agent_eval/general_agents/`: agent adapters (claude-code, codex).
- `src/general_agent_eval/orchestration/`: Docker run orchestrator — staging,
  preprocessing pipeline, image build/run, and run manifests.
- `src/general_agent_eval/preprocessing/`: input preprocessing utilities.
- `src/general_agent_eval/recovery/`: rebuild agent outputs into the full repo.
- `src/general_agent_eval/prompts/`: packaged Jinja prompt templates.
- `docker/`: layered Dockerfiles for the runtime image stack (base + agent +
  workload + service overlays).
- `runs/`: default parent directory for generated run outputs.

## Environment

This project uses `uv` with a Hatchling build backend.

```bash
uv sync
uv run pytest
```

## Claude Code Runner

Run Claude Code directly against an input directory:

```bash
uv run general-agent-eval-claude-code \
  --input-dir /path/to/project \
  --model sonnet
```

The runner denies `WebSearch` and `WebFetch`, sets the input directory as the
agent working directory, defaults Claude Code to `bypassPermissions`, and
renders the packaged prompt templates from `src/general_agent_eval/prompts/`.

`--small-model` overrides Claude Code's small/fast model (mapped to
`ANTHROPIC_SMALL_FAST_MODEL`). That model only handles auxiliary background work
— conversation titles, summaries, topic detection — never the main agent loop or
subagents, and defaults to Haiku 4.5 when unset. Set it (e.g. to `--model`'s
value) to keep a run on a single model or to pin a gateway-specific model ID.

When `--base-url` is set (a custom/non-Anthropic gateway), the runner defaults
`CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1` so Claude Code stops sending
`anthropic-beta` headers the gateway would reject. Pass
`--env CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=0` to re-enable them for a
beta-capable endpoint.

## OpenAI Codex Runner

Run OpenAI Codex directly against an input directory:

```bash
uv run general-agent-eval-codex \
  --input-dir /path/to/project \
  --model gpt-5-codex \
  --api-key-env OPENAI_API_KEY
```

The runner wraps the official `openai-codex` Python SDK (its native binary ships
bundled with the dependency, so no separate install is needed) and renders the
same packaged prompt templates as the Claude Code runner. `--model` is required;
there is no default.

`--system-prompt-config` maps the rendered system template onto Codex:
`replace` (default) uses it as `base_instructions` (a full replacement of Codex's
built-in prompt), `append` adds it as `developer_instructions`, and `none` uses
neither. `--sandbox` controls Codex's filesystem/network access. The standalone
runner defaults to `workspace_write` because direct runs execute on the host; raise
it to `full_access` or lower it to `read_only` as needed. (Under
`general-agent-eval-docker-run` it instead defaults to `full_access`, since the
container — `cap-drop ALL`, `no-new-privileges` — is the real security boundary.)
Pass `--base-url` to point Codex at a custom OpenAI-compatible gateway
(authenticated via `OPENAI_API_KEY`).

Codex reports token usage and duration but **no dollar cost**, so the result
record and `manifest.json` carry `total_cost_usd: null` plus a `usage` token
breakdown — consult the provider's billing dashboard for actual spend.

## Docker Runner

Run an agent inside the shared Docker runtime against a disposable staged copy:

```bash
uv run general-agent-eval-docker-run \
  --agent claude-code \
  --input-dir /path/to/project \
  --reset-git \
  --clear-tests \
  --model sonnet \
  --api-key-env ANTHROPIC_API_KEY
```

Pass `--agent codex` to run OpenAI Codex instead. `--model` is required for it,
and `--sandbox` (default `full_access`) selects the Codex sandbox mode:

```bash
uv run general-agent-eval-docker-run \
  --agent codex \
  --input-dir /path/to/project \
  --reset-git \
  --clear-tests \
  --model gpt-5-codex \
  --api-key-env OPENAI_API_KEY
```

Options that apply to a single agent are rejected (rather than silently dropped)
when passed for the other agent: `--permission-mode`, `--auth-token-env`,
`--oauth-token-env`, `--max-budget-usd`, `--small-model`, and `--extra-arg` are
claude-code only, while `--sandbox` is codex only. Shared options (`--model`,
`--system-prompt-config`, `--system-template`, `--user-template`,
`--prompt-var`, `--base-url`, `--api-key-env`, `--env`) work for both.

### Custom prompts

The Docker runner forwards the same prompt controls as the standalone runners.
`--system-template` and `--user-template` take host paths to Jinja2 templates;
each template's directory is bind-mounted read-only into the container, so
`{% include %}` of sibling templates keeps resolving. `--prompt-var KEY=VALUE`
(repeatable) injects extra template variables. Without these flags the packaged
Java test-generation prompts are used, as before. Keys reserved by the template
context (`input_dir`, `model`, ...) are rejected up front, as are keys the
orchestrator derives from `--service` (`service_base_url`, ...), since
overriding those would desync the prompt from the live service.

### Runtime image stack

The runtime image is composed from layered Dockerfiles under `docker/`, each
building `FROM ${BASE_IMAGE}` on top of the previous one, so a run only carries
the toolchains it needs:

- `Dockerfile.base` — Python, the harness package and its dependencies, the
  non-root agent user, and general CLI tooling. Everything else builds on it.
- `Dockerfile.claude-code` / `Dockerfile.codex` — the per-agent layer. claude-code
  adds Node.js and the `claude` CLI; codex adds only `bubblewrap` (its binary
  ships in the `openai-codex-cli-bin` wheel installed in the base).
- `Dockerfile.java` — the default workload layer: the JDK/build toolchain
  (Temurin 17 + 8, Gradle, Maven) for the Java evaluation targets.
- `Dockerfile.javascript` — the JavaScript workload layer: Node 20 LTS and the
  OS-level browser dependencies Playwright needs. The Playwright browser binaries
  are not pre-installed; `npx playwright install <browser>` runs inside the project
  repo at agent-run time so the version matches the project's pinned dependency. OS
  deps are pre-installed as root so the non-root agent user can run browsers without
  `--with-deps`.
- `Dockerfile.genome-nexus` — a service overlay adding the MongoDB server, built
  only when `--service genome-nexus` is selected.

By default a run builds `base + <agent> + java` (plus `genome-nexus` for that
service) in order and runs the final layer, tagged e.g.
`general-agent-eval-claude-code-java:latest`. Pass `--workload javascript` to build
and run `base + <agent> + javascript` instead (`general-agent-eval-claude-code-javascript:latest`). The base layer's build context is
the project source (it `COPY`s `src`/`pyproject.toml`), so the default build runs
from a source checkout; an installed wheel does not bundle `docker/` and the
orchestrator says so rather than probing the caller's cwd. Two flags override this:

- `--image NAME` names a pre-built image to run and skips the build entirely
  (e.g. from a registry or an earlier build).
- `--dockerfile PATH` builds a single custom Dockerfile instead of the composed
  stack. The build context is the Dockerfile's own directory, and the image is
  tagged with `--image` (or the default tag when omitted). Conflicts with
  `--skip-build`.

Any image — composed default or custom — must satisfy the runtime contract the
orchestrator assumes: a non-root user whose UID/GID match the host user (staged
input and output are bind-mounted read-write), `bash` and `git` on PATH, the
agent tooling for the selected agent (the `claude` CLI for claude-code; the
codex binary ships inside the `openai-codex-cli-bin` wheel), and Python 3.11+
with this project's dependencies importable plus `PYTHONPATH=/app/src` — the
repository itself is mounted read-only at `/app` and the agent entrypoint is
`python -m general_agent_eval.general_agents.<agent>`. The `manifest.json`
`docker` block records the effective image, whether it was built, and the
ordered `layers` chain that produced it (empty when a pre-built image ran).

Runs are written under `runs/<timestamp>__<agent>__<project>` by default. Pass
`--output-dir` to choose a different parent directory. After completion,
`manifest.json` includes a compact `agent_result` summary with cost, duration,
and turn count when the selected agent reports those fields (the codex agent
reports duration and token `usage` but a null `total_cost_usd`).

To run against a live service, pass the service manifest and scripts directory
explicitly:

```bash
uv run general-agent-eval-docker-run \
  --input-dir /path/to/service-repo \
  --service genome-nexus \
  --service-manifest /path/to/resources/scripts/services.json \
  --service-scripts-dir /path/to/resources/scripts \
  --clear-tests \
  --model sonnet \
  --api-key-env ANTHROPIC_API_KEY
```

`--service-scripts-dir` must contain `run-with-service.sh`. If
`--service-manifest` is omitted, the runner uses
`--service-scripts-dir/services.json`.

### JavaScript / Playwright UI test generation

To generate Playwright E2E tests against a JavaScript frontend, use
`--workload javascript`. This selects `Dockerfile.javascript` as the workload
layer and switches the default prompts to the UI-focused Playwright templates. Pair
it with `--service` and the in-repo service scripts to start the app inside the
container before the agent runs:

```bash
uv run general-agent-eval-docker-run \
  --workload javascript \
  --agent claude-code \
  --input-dir /path/to/js-frontend \
  --service my-js-app \
  --service-scripts-dir resources/scripts \
  --clear-tests \
  --model sonnet \
  --auth-token-env ANTHROPIC_AUTH_TOKEN
```

`resources/scripts/` is the in-repo service scripts directory. It contains:
- `run-with-service.sh` — a minimal service runner that parses `services.json`,
  runs `npm ci` build steps, health-gates the dev server, exports
  `SERVICE_BASE_URL` and `PLAYWRIGHT_BASE_URL`, then exec's the agent command.
- `services.json` — service definitions. Add an entry per JS project with
  `build`, `run`, `default_port`, `health_path`, and `health_timeout_seconds`.

See `resources/scripts/services.json` for the `sample-js-app` example entry.
`--inject-rest-assured` requires `--workload java` and is rejected otherwise.

### Injecting RestAssured

Add `--inject-rest-assured` (requires `--service`) to provision RestAssured as a
test dependency before the agent runs, so generated HTTP tests can use it without
the agent wiring up the build itself. The per-service coordinates, target POM
(the module whose tests run), and version live in the service manifest's optional
`rest_assured` block; omit the block to skip injection. The version is `null` for
Spring Boot services (inherited from the Boot dependency-management BOM) and an
explicit string otherwise. An optional `exclusions` list (`group_id`/`artifact_id`
entries) strips transitive dependencies that would clash with the host project,
e.g. under a maven-enforcer `dependencyConvergence` rule. The POM edit runs after
`--clear-tests` and lands in the baseline with target tests removed, so it stays
out of the agent's `git_diff.patch`; the change is captured separately as
`output/dependency_injection.patch`, which the recoverer replays onto the cloned
original repo before the agent patch.

With the flag set, the user prompt also tells the agent to use RestAssured, and for
a multi-module target it names the module to put the tests in (derived from the
`rest_assured.target_pom` directory). Single-module projects see no module note.

## Recovering Agent Outputs

A run's `input/` directory is the agent's live working directory after target
tests have been cleared. The pre-agent state is preserved as the synthetic
baseline commit, and `output/git_diff.patch` captures the agent's changes
against it. To evaluate the agent's generated tests inside the complete project,
re-base that patch onto the original repository:

```bash
uv run general-agent-eval-recover \
  --run-dir runs/<timestamp>__claude-code__<project> \
  --repo path/to/cloned/project
```

The recoverer clones `--repo` (the original local checkout you passed to the
run's `--input-dir`), checks out the commit recorded in `manifest.json` (the
`--reset-git` pinned commit, otherwise the cleared-tests baseline's
`original_head`; override with `--commit`), and applies
`git_diff.patch` onto that full tree. The agent's patch is taken against the
baseline with target tests removed, so the only conflicts are paths the agent
recreated that were cleared from the original; the agent's version wins those
collisions. Results land in `<run-dir>/recovered/<project>/` (override the parent with
`--output-dir`) alongside a `recovery_manifest.json` that records the commit,
collisions resolved, any non-test/production-code paths the patch touched, and
caveats (e.g. runs without `--reset-git` whose baseline may diverge from a clean
clone).
