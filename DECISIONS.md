# Architecture Decision Record

**Repository:** `databricks-llm-judge-builder`
**Forked from:** `databricks-solutions/judge-builder`
**Primary author:** Samraj Moorjani (Databricks)
**Last updated from evidence:** 2025-10-31 (latest substantive commit: `1c911ca`)

---

## DEC-001: DSPy SIMBA as the Judge Alignment Engine

**Status:** Decided (superseded an earlier approach)
**Date:** 2025-09-16 (commit `3e5e477`, integration with MLflow `make_judge` and `align`)
**Evidence:** `src/server/judges/custom_simba_optimizer.py`, `src/server/judges/instruction_judge.py`, `src/server/utils/dspy_utils.py`, `src/server/utils/constants.py`, `src/pyproject.toml`, deleted files `server/optimizers/custom_prompt_optimizer.py` and `server/judges/custom_prompt_judge.py` (commit `3e5e477`)

### Context

The platform needs to close the agreement gap between a zero-shot judge instruction and human SME labels. Manual prompt iteration is too slow and produces inconsistent results across judge instances. An automated optimizer that takes labeled traces and produces an improved instruction is required.

### Options Considered

| Option | Evidence it was considered | Why not chosen (if known) |
|---|---|---|
| DSPy SIMBA via MLflow `SIMBAAlignmentOptimizer` | Current implementation: `custom_simba_optimizer.py` extends `mlflow.genai.judges.optimizers.simba.SIMBAAlignmentOptimizer` | — (chosen) |
| DSPy MIPROv2 via custom `CustomPromptOptimizer` | Deleted file `server/optimizers/custom_prompt_optimizer.py` (commit `3e5e477`); `src/server/utils/constants.py` line 8: `DEFAULT_JUDGE_OPTIMIZER = 'miprov2'` (residual constant) | Replaced when MLflow 3.4.0 introduced `make_judge().align()` with built-in SIMBA support; the custom MIPROv2 wrapper was redundant |
| Manual few-shot prompt construction | No evidence considered |
| Model fine-tuning | No evidence considered |

### Decision

SIMBA (via MLflow's `SIMBAAlignmentOptimizer`) replaced a custom MIPROv2 DSPy optimizer in commit `3e5e477`. The migration was driven by MLflow 3.4.0 introducing `make_judge()` and `align()` as first-class APIs — using MLflow's built-in optimizer eliminated ~550 lines of custom optimization code (`custom_prompt_optimizer.py`, `custom_prompt_judge.py`). `CustomSIMBAAlignmentOptimizer` extends `SIMBAAlignmentOptimizer` only to substitute the language model: it replaces MLflow's `construct_dspy_lm` with a custom `AgentEvalLM` that routes through Databricks' `managed_rag_client` (or LiteLLM for custom endpoints).

The optimizer calls `self._dspy_optimize(program, dspy_examples, agreement_metric)` where `agreement_metric` is imported from `mlflow.genai.judges.optimizers.dspy_utils`. The DSPy program's `signature.instructions` field is the optimization target — only the instruction text changes, not the model.

### Consequences

**Accepted tradeoffs:**
- Tight coupling to MLflow's SIMBA implementation. The `_dspy_optimize`, `_get_dspy_program_from_judge`, `agreement_metric`, and `trace_to_dspy_example` functions are all imported from `mlflow.genai.judges.optimizers` internals (not public API surface). An MLflow minor version bump can break these imports.
- The residual `DEFAULT_JUDGE_OPTIMIZER = 'miprov2'` constant in `constants.py` is dead code — it is not referenced anywhere in the optimizer path. The actual optimizer is always SIMBA.
- `AgentEvalLM` extends `dspy.BaseLM` and hardcodes `super().__init__('databricks/databricks-llama-4-maverick')` as a model identifier string, though the actual model used is `self.model` (default `gpt-oss-120b`). The parent class init string appears to be a placeholder.

**What this locks in:**
- DSPy 2.x API (the `dspy.BaseLM` interface, `dspy.context(lm=...)` context manager)
- MLflow ≥3.4.0 with `mlflow.genai.judges.optimizers.simba` module
- The optimization output is always a new instruction string, never few-shot examples or model weights

### Deferred / Open

- `src/server/utils/constants.py:8` — `DEFAULT_JUDGE_OPTIMIZER = 'miprov2'` is unreferenced dead code that should be removed or updated to `'simba'`.
- `src/server/utils/dspy_utils.py:41` — `AgentEvalLM.__init__` passes `'databricks/databricks-llama-4-maverick'` to `super().__init__()` regardless of the actual model. This is a placeholder for the parent class requirement.
- `src/server/utils/dspy_utils.py:50` — `AgentEvalLM.load_state` is `pass` (no-op).

---

## DEC-002: MLflow 3.x `list_scorers()` / `register()` as the Judge Delivery Mechanism

**Status:** Decided
**Date:** 2025-09-16 (commit `3e5e477`, when `InstructionJudge` replaced `CustomPromptJudge`)
**Evidence:** `src/server/judges/instruction_judge.py:37-40` (`make_judge`), `instruction_judge.py:83-122` (`register_scorer`), `src/server/services/alignment_service.py:52-66` (`list_scorers`), `README.md:36-43`

### Context

Judges created in the platform must be usable outside of it — in offline evaluation pipelines via `mlflow.genai.evaluate()` and in online evaluation attached to MLflow experiments. The delivery mechanism determines how a judge is consumed downstream.

### Options Considered

| Option | Evidence it was considered | Why not chosen (if known) |
|---|---|---|
| MLflow scorer via `make_judge()` + `register()` + `list_scorers()` | Current implementation throughout `instruction_judge.py` and `alignment_service.py` | — (chosen) |
| Standalone Python class (pre-MLflow integration) | Deleted `server/judges/custom_prompt_judge.py` managed its own DSPy `ChainOfThought` program without MLflow registration | Replaced to use MLflow's native judge ecosystem |

### Decision

Judges are created via `mlflow.genai.judges.make_judge(name, instructions)` which returns a `Judge` object that acts as an MLflow scorer. Registration happens via `scorer_func.register(name=scorer_name, experiment_id=experiment_id)`. Consumers retrieve judges via `mlflow.genai.scorers.list_scorers()`. The scorer name follows the pattern `{sanitized_name}_v{version}` (from `naming_utils.create_scorer_name`).

This was chosen because MLflow 3.x's scorer API is the canonical way to attach evaluators to Databricks experiments. The alternative (custom Python classes) would have required consumers to install this application's code to use a judge.

### Consequences

**Accepted tradeoffs:**
- Requires `mlflow[databricks]>=3.5.0` (pinned in `pyproject.toml`). The `make_judge`, `align`, and `list_scorers` APIs are recent additions — older MLflow installations cannot consume these judges.
- The scorer registration calls Databricks Jobs API internally (evidenced by the `PERMISSION_DENIED` handling in `instruction_judge.py:102-118` which parses job IDs from error messages). This means scorer registration requires the user to have job creation permissions.
- The scorer interface expects `inputs`/`outputs` dicts or a `trace` object. The judge cannot accept arbitrary input formats.

**What this locks in:**
- All judge consumers must be on MLflow ≥3.5.0 with Databricks backend
- Scorer names are globally scoped within an experiment — name collisions between judges are possible
- The `register()` call creates a Databricks Job under the hood — this is an external side effect of judge creation

### Deferred / Open

None identified.

---

## DEC-003: Full-Stack Web Application vs. Notebook-Only Approach

**Status:** Decided
**Date:** 2025-08-24 (commit `443dd12`, initial commit with FastAPI + React)
**Evidence:** `src/server/app.py`, `src/client/`, `deploy.sh`, `src/app.yaml`, `src/manifest.yaml`, `README.md`

### Context

The platform requires an SME labeling workflow where non-technical domain experts provide human feedback on traces. This is a multi-user, multi-session process with state that persists across visits.

### Options Considered

| Option | Evidence it was considered | Why not chosen (if known) |
|---|---|---|
| FastAPI + React SPA deployed as Databricks App | Current implementation. `src/app.yaml` starts `uvicorn server.app:app`. `deploy.sh` deploys via `databricks apps deploy`. | — (chosen) |
| Notebook-based UI | No evidence considered |
| Streamlit / Gradio | No evidence considered |

No evidence of alternatives considered. The chosen approach appears in the initial implementation without documented alternatives.

### Decision

A full-stack web application was built from the initial commit. The deployment target is Databricks Apps (`deploy.sh` calls `databricks apps create` and `databricks apps deploy`). In production, FastAPI serves the React build as static files from `client/build/` with SPA fallback routing. The labeling workflow requires a persistent, multi-page UI with state management (experiment selection → trace browsing → labeling → alignment review) that exceeds what notebook widgets or Streamlit provide.

### Consequences

**Accepted tradeoffs:**
- Operational complexity: requires Node.js 18+ and npm in addition to Python. Two build systems (Vite for frontend, hatchling for Python package).
- No notebook integration: data scientists working in notebooks must switch context to the web UI for labeling and alignment, then switch back to notebooks for `list_scorers()`.
- The app runs as a single Databricks App instance — no horizontal scaling or multi-tenancy isolation is implemented.

**What this locks in:**
- Databricks Apps as the deployment platform (the `databricks apps deploy` CLI command, the `app.yaml` format)
- A Node.js build step in the deployment pipeline
- CORS configuration required for development mode (Vite on `:5173`, FastAPI on `:8000`)

### Deferred / Open

- `src/server/app.py:109` — `yield` / `pass` in lifespan shutdown: no cleanup logic implemented.

---

## DEC-004: FastAPI as the Backend Framework

**Status:** Decided
**Date:** 2025-08-24 (commit `443dd12`)
**Evidence:** `src/server/app.py`, `src/server/routers/`, `src/server/models.py`, `src/pyproject.toml`, `src/app.yaml`

### Context

The backend must serve both the React frontend's API needs (CRUD for judges, labeling sessions, alignment runs) and generate an OpenAPI schema for automatic TypeScript client generation.

### Options Considered

| Option | Evidence it was considered | Why not chosen (if known) |
|---|---|---|
| FastAPI with uvicorn | Current implementation. `app.yaml` runs `uvicorn server.app:app`. | — (chosen) |

No evidence of alternatives considered.

### Decision

FastAPI was chosen. All routes use `async def` but the actual service implementations are synchronous (no `await` calls in service methods). The primary value of FastAPI here is: Pydantic model integration for request/response validation (27 Pydantic models in `models.py`), automatic OpenAPI schema generation (consumed by `scripts/make_fastapi_client.py` to generate the TypeScript client), and `BackgroundTasks` for the alignment endpoint (commit `c212f3f`).

The server starts with `uvicorn` with `--reload` in development. Production deployment uses the same single-worker uvicorn (no gunicorn wrapper, no worker scaling).

### Consequences

**Accepted tradeoffs:**
- Single-worker uvicorn means alignment runs block the process. The background task pattern (commit `c212f3f`) moved alignment to a background thread, but it still runs in the same process. A long alignment run on a small instance could starve other requests.
- No authentication middleware. The app relies on Databricks Apps' built-in auth proxy — there is no auth check in the FastAPI code itself.

**What this locks in:**
- Pydantic v2 data model format for all API contracts
- OpenAPI 3.x schema as the contract between backend and frontend
- `uvicorn` as the ASGI server

### Deferred / Open

None identified.

---

## DEC-005: shadcn/ui + Tailwind CSS as the Frontend Component System

**Status:** Decided
**Date:** 2025-08-24 (commit `443dd12`)
**Evidence:** `src/client/package.json`, `src/client/tailwind.config.js`, `src/client/src/components/ui/`

### Context

The frontend needs form controls (inputs, selects, checkboxes), data display (cards, tables, badges), and feedback components (toasts, tooltips, dialogs) for the judge management workflow.

### Options Considered

| Option | Evidence it was considered | Why not chosen (if known) |
|---|---|---|
| shadcn/ui (Radix primitives) + Tailwind CSS | Current implementation. Components copied into `components/ui/`. | — (chosen) |

No evidence of alternatives considered.

### Decision

shadcn/ui components are copied as source files into `src/client/src/components/ui/` — the shadcn/ui model of owning the component source rather than importing from a package. The Radix UI primitives used: checkbox, dialog, dropdown-menu, icons, label, popover, progress, select, slot, tabs, toast, tooltip (12 packages in `package.json`). Tailwind configuration uses HSL CSS variables (`--background`, `--foreground`, `--primary`, etc.) with a `calc()`-based border radius system. The color system is neutral/gray — no Databricks brand colors.

### Consequences

**Accepted tradeoffs:**
- Components are local copies, not versioned packages. Upgrading shadcn/ui requires manually re-copying components and reconciling changes.
- No Databricks design system integration. The app looks like a generic modern web app, not a native Databricks experience.

**What this locks in:**
- Tailwind CSS as the styling system (all components use Tailwind utility classes)
- Radix UI as the accessibility/behavior layer
- The `cn()` utility (`clsx` + `tailwind-merge`) as the class merging pattern throughout all components

### Deferred / Open

None identified.

---

## DEC-006: uv for Python Dependency Management

**Status:** Decided
**Date:** 2025-08-24 (commit `443dd12`)
**Evidence:** `setup.sh`, `deploy.sh`, `src/dev/watch.sh`, `uv.lock`, `src/pyproject.toml`

### Context

The project needs a Python package manager that can resolve dependencies from `pyproject.toml`, create virtual environments, and produce a lockfile for reproducible builds.

### Options Considered

| Option | Evidence it was considered | Why not chosen (if known) |
|---|---|---|
| uv | Current implementation throughout shell scripts and lockfile | — (chosen) |

No evidence of alternatives considered.

### Decision

`uv` is used for virtual environment creation (`uv venv --python 3.11`), dependency installation (`uv pip install -r`), and running commands in the project context (`uv run --project src`). `setup.sh` installs uv automatically if not present (`curl -LsSf https://astral.sh/uv/install.sh | sh`). The `--project src` flag is required on all `uv run` commands because `pyproject.toml` lives under `src/` (established in the marketplace restructure, commit `1c911ca`).

### Consequences

**Accepted tradeoffs:**
- `uv` is not present on standard Databricks runtimes or most CI images. Every fresh environment must install it first.
- The `uv.lock` file is ~800KB, considerably larger than typical `requirements.txt` lockfiles.
- Deployment generates a `requirements.txt` from `pyproject.toml` via `scripts/generate_semver_requirements.py` rather than using `uv.lock` directly — the deployed Databricks App uses `pip`, not `uv`.

**What this locks in:**
- Local development requires `uv` (installed globally)
- The `--project src` flag is mandatory for all `uv run` invocations due to the `src/` directory structure

### Deferred / Open

None identified.

---

## DEC-007: Shell Scripts (setup.sh / deploy.sh) vs. Databricks Asset Bundles

**Status:** Decided
**Date:** 2025-08-24 (commit `443dd12`)
**Evidence:** `setup.sh`, `deploy.sh`, `src/manifest.yaml`, `src/app.yaml`

### Context

The application must be deployed to a Databricks workspace as a running app. Deployment involves building the frontend, syncing source code, creating the app resource, and deploying.

### Options Considered

| Option | Evidence it was considered | Why not chosen (if known) |
|---|---|---|
| Shell scripts (`setup.sh`, `deploy.sh`) calling Databricks CLI | Current implementation | — (chosen) |

No evidence of Databricks Asset Bundles (DAB) considered. There is no `databricks.yml` in the repository. The `manifest.yaml` is a Databricks Marketplace manifest (name/description only), not a DAB configuration.

### Decision

Shell scripts orchestrate the full deployment: `setup.sh` configures the local environment (uv, npm, Databricks CLI profile, `.env.local`), and `deploy.sh` builds the frontend (`npm run build`), generates `requirements.txt`, writes `app.yaml`, creates workspace directories (`databricks workspace mkdirs`), syncs code (`databricks sync --full`), creates the app if needed (`databricks apps create`), and deploys (`databricks apps deploy`).

The `app.yaml` is generated dynamically by `deploy.sh` with the `JUDGE_OPTIMIZER` env var (currently hardcoded to `simba`). The startup command is `uvicorn server.app:app`.

### Consequences

**Accepted tradeoffs:**
- No infrastructure-as-code versioning. The deployment state exists only in the Databricks workspace, not in a declarative configuration file.
- `setup.sh` is interactive (prompts for profile name and app name) — cannot be used in CI without modification.
- `databricks sync --full` copies all files under `src/` to the workspace, including test files and development scripts.

**What this locks in:**
- Databricks CLI as the deployment tool (specifically `databricks apps create`, `databricks apps deploy`, `databricks sync`, `databricks workspace mkdirs`)
- The `.env.local` file as the configuration store for `DATABRICKS_CONFIG_PROFILE`, `DATABRICKS_APP_NAME`, and `DATABRICKS_SOURCE_CODE_PATH`
- A single-app deployment model (one app name per workspace)

### Deferred / Open

- `deploy.sh:98` — `JUDGE_OPTIMIZER` env var in `app.yaml` is hardcoded to `simba`. The variable is written to `app.yaml` but is not read anywhere in the server code. `DEFAULT_JUDGE_OPTIMIZER` in `constants.py` is also not referenced.

---

## DEC-008: Judge Alignment Workflow — Create → Label → Align → Deploy

**Status:** Decided
**Date:** 2025-08-24 (commit `443dd12`, refined through `3e5e477`, `c212f3f`)
**Evidence:** `src/server/services/alignment_service.py:347-445`, `src/server/routers/alignment.py`, `src/server/services/judge_service.py:182-221`, `README.md:29-34`

### Context

Judge optimization requires human feedback data. The workflow must collect labeled examples before optimization can run, and must preserve the ability to compare pre- and post-alignment judge performance.

### Options Considered

| Option | Evidence it was considered | Why not chosen (if known) |
|---|---|---|
| Stateful 4-step workflow (create → label → align → deploy) | Current implementation | — (chosen) |

No evidence of alternatives considered.

### Decision

The workflow is enforced by data dependencies, not explicit state machine guards:

1. **Create**: `judge_service.create_judge()` creates an `InstructionJudge` and stores it in memory (`_judges` dict) and as MLflow experiment tags.
2. **Label**: Traces are added to a labeling session via `labeling_service`. Human feedback is collected through the Databricks managed evals labeling UI (external to this app).
3. **Align**: `alignment_service.run_alignment()` executes a 6-step sequence: evaluate current version → get alignment model config → optimize via SIMBA → create new version → evaluate new version → tag labeling run.
4. **Deploy**: Automatic — `judge_service.create_new_version()` calls `register_scorer()` which makes the judge available via `list_scorers()`.

State is persisted in three places: in-memory `_judges` dict (ephemeral, reloaded from MLflow on startup via `load_all_judges_on_startup`), MLflow experiment tags (JSON blob under `judges` tag), and MLflow runs/traces (evaluation results, labeling feedback).

### Consequences

**Accepted tradeoffs:**
- In-memory judge storage means all judges must be reconstructed from MLflow metadata on every application restart. `load_all_judges_on_startup()` handles this but adds startup latency.
- The TODO at `judge_service.py:263` indicates that recreated judges may not have their optimized instructions restored: `# TODO: We may need to recreate the judge with optimized instructions if needed`.
- Alignment comparison requires version ≥ 2 (`alignment_service.py:199`), so the first alignment produces a v1→v2 comparison. There is no mechanism to compare across non-adjacent versions (e.g., v1 vs v3).
- Deployment is automatic and immediate. There is no staging, review, or approval step between alignment and scorer availability.

**What this locks in:**
- MLflow experiment tags as the persistence layer for judge metadata (JSON string, subject to tag size limits)
- The `agreement_metric` from MLflow's DSPy utils as the single optimization objective
- Sequential version numbering (no branching, no parallel alignment experiments)

### Deferred / Open

- `src/server/services/judge_service.py:263` — `# TODO: We may need to recreate the judge with optimized instructions if needed` — recreated judges use `user_instructions` (original), not `system_instructions` (aligned).
- `src/server/services/alignment_service.py:90,141` — `evaluation_results=[]  # TODO: Implement individual trace results` — individual per-trace evaluation results are not populated in `EvaluationResult`.

---

## DEC-009: Human Label Collection via Databricks Managed Evals

**Status:** Decided
**Date:** 2025-08-24 (commit `443dd12`)
**Evidence:** `src/server/services/labeling_service.py` (imported from agents but not fully shown), `src/server/models.py:119-128` (`LabelingProgress`), `src/server/models.py:299-329` (`CreateLabelingSessionRequest`, `LabelingSessionInfo`)

### Context

Domain SMEs must provide human feedback on agent traces to create alignment training data. This requires a labeling interface that non-technical users can access.

### Options Considered

| Option | Evidence it was considered | Why not chosen (if known) |
|---|---|---|
| Databricks managed evals labeling UI via `databricks-agents` SDK | Current implementation. `databricks-agents>=1.8.0` in `pyproject.toml`. | — (chosen) |

No evidence of alternatives considered.

### Decision

The platform uses Databricks' managed evaluation labeling infrastructure (via `databricks-agents` package). The labeling session is created by the `labeling_service` and produces a `labeling_url` that SMEs visit to provide feedback. The labeling UI is external to this application — this app creates sessions, adds traces to them, and reads back the labels. Schema is inferred from the judge instruction via `extract_categorical_options_from_instruction()`, defaulting to binary `['Pass', 'Fail']`.

Labels are stored as MLflow assessments on traces with `source_type='HUMAN'`. Inter-annotator agreement is not computed. Multiple SME labels on the same trace are not aggregated — the system reads the first matching human assessment via `get_human_feedback_from_trace()`.

### Consequences

**Accepted tradeoffs:**
- External labeling UI dependency. The labeling experience is controlled by Databricks, not by this application. UI changes in `databricks-agents` are outside the platform's control.
- No inter-annotator agreement measurement. If two SMEs disagree, only one label is used.
- SME emails are passed during session creation but access control is delegated to the managed evals platform.

**What this locks in:**
- `databricks-agents>=1.8.0` as a hard dependency
- MLflow assessment schema for label storage (assessment name must match sanitized judge name)
- Binary or categorical labels only — no free-text feedback, no pairwise comparison

### Deferred / Open

None identified.

---

## DEC-010: MLflow Experiment as the Source of Traces

**Status:** Decided
**Date:** 2025-08-24 (commit `443dd12`)
**Evidence:** `src/server/services/experiment_service.py`, `src/server/utils/parsing_utils.py`, `src/server/models.py:69-107` (`TraceExample`)

### Context

Judges evaluate agent responses. The system needs a source of (request, response) pairs with traceability to the originating agent run.

### Options Considered

| Option | Evidence it was considered | Why not chosen (if known) |
|---|---|---|
| MLflow experiment traces | Current implementation | — (chosen) |

No evidence of alternatives considered (no CSV upload, no direct API input, no Delta table ingestion).

### Decision

Traces are read from MLflow experiments via the `experiment_service`. The `parsing_utils` module extracts request and response text from trace objects with fallback chains: for requests it tries `trace.data.request`, then `trace.info.request_preview`, then scans for keys (`query`, `input`, `prompt`, `message`, `text`). The same fallback pattern applies to responses. This design accommodates different agent trace schemas without requiring a canonical format.

### Consequences

**Accepted tradeoffs:**
- Traces must be in MLflow. There is no way to evaluate arbitrary (question, answer) pairs without first logging them as MLflow traces.
- The parsing fallback chain in `parsing_utils.py` handles heterogeneous trace schemas but can silently extract the wrong field if a trace has both `query` and `input` keys with different content.
- Trace caching (`cache_service`) uses a TTL-based in-memory cache. On application restart, all cached traces are lost and must be re-fetched from MLflow.

**What this locks in:**
- MLflow trace format as the input schema
- The `trace_id` as the primary key linking examples, labels, and evaluation results
- The `cache_service` as an intermediate layer between all trace consumers and MLflow

### Deferred / Open

None identified.

---

## DEC-011: Single Judge Type — InstructionJudge

**Status:** Decided (superseded)
**Date:** 2025-09-16 (commit `3e5e477`, replaced `CustomPromptJudge`)
**Evidence:** `src/server/judges/base_judge.py`, `src/server/judges/instruction_judge.py`, `src/server/utils/schema_analysis.py`

### Context

The platform must support judges that evaluate different dimensions (relevance, faithfulness, safety, etc.) with different output schemas (binary, categorical, ordinal).

### Options Considered

| Option | Evidence it was considered | Why not chosen (if known) |
|---|---|---|
| `InstructionJudge` wrapping `mlflow.genai.judges.make_judge()` | Current implementation | — (chosen) |
| `CustomPromptJudge` with DSPy `ChainOfThought` | Deleted in commit `3e5e477` | Replaced by MLflow's native judge API |

### Decision

There is one judge implementation: `InstructionJudge`. It wraps `mlflow.genai.judges.make_judge(name, instructions)` which creates a scorer from free-form natural language instructions. The judge type, evaluation dimension, and output schema are all determined by the instruction text. `schema_analysis.py` infers the output schema by parsing the instruction for patterns (quoted options, numbered lists, bullet points) with a binary `['Pass', 'Fail']` fallback.

The `BaseJudge` ABC defines `_create_scorer()`, `evaluate()`, and `register_scorer()` as abstract methods, suggesting extensibility — but no other implementations exist.

### Consequences

**Accepted tradeoffs:**
- No specialized judge types. A faithfulness judge and a safety judge use the same code path, differentiated only by instruction text. This means the platform cannot apply type-specific optimization strategies.
- Schema inference from natural language is heuristic. `extract_categorical_options_from_instruction()` uses regex patterns and defaults to binary if parsing fails. A carefully worded instruction that does not match the patterns will be treated as binary.
- Built-in Databricks judges (relevance, faithfulness, safety) are not directly integrated. The platform creates custom judges only.

**What this locks in:**
- `mlflow.genai.judges.make_judge()` as the sole judge factory
- Natural language as the only judge configuration interface (no structured judge definitions)
- Binary pass/fail as the default output schema

### Deferred / Open

- `src/server/judges/base_judge.py` — `BaseJudge` ABC exists but has only one implementation. The abstraction is preparatory.

---

## DEC-012: Databricks Workspace Integration Surface

**Status:** Decided
**Date:** 2025-08-24 (commit `443dd12`)
**Evidence:** `src/server/services/base_service.py`, `src/server/utils/dspy_utils.py`, `src/server/services/serving_endpoint_service.py`, `setup.sh`, `deploy.sh`

### Context

The application must authenticate to Databricks for MLflow tracking, serving endpoint access, and user identity.

### Options Considered

| Option | Evidence it was considered | Why not chosen (if known) |
|---|---|---|
| Databricks SDK with profile-based auth + managed RAG client | Current implementation | — (chosen) |

No evidence of alternatives considered.

### Decision

Authentication supports two modes: token-based (`DATABRICKS_HOST` + `DATABRICKS_TOKEN`) and OAuth (`DATABRICKS_HOST` + `DATABRICKS_CLIENT_ID` + `DATABRICKS_CLIENT_SECRET`), validated in `base_service.py:32-47`. In deployment, the Databricks App provides credentials automatically. In development, `setup.sh` configures a Databricks CLI profile stored in `.env.local`.

The `AgentEvalLM` routes all LLM calls through `databricks.rag_eval.context.get_context().build_managed_rag_client()`, which uses the Databricks-managed RAG evaluation infrastructure. The default model is `gpt-oss-120b`. Custom models use LiteLLM via the `databricks:/endpoint-name` format.

The Databricks SDK is imported in `instruction_judge.py:86` (`from databricks.sdk import WorkspaceClient`) for user-facing error message enrichment (parsing job IDs from permission errors). It is not used for core judge operations.

### Consequences

**Accepted tradeoffs:**
- Tight coupling to Databricks' managed RAG infrastructure. `AgentEvalLM` cannot function without a Databricks workspace context.
- No multi-workspace support. `mlflow.set_tracking_uri('databricks')` in `base_service.py` sets a single tracking URI globally.
- Auth validation in `_validate_auth()` logs an error but does not raise — the application starts even with missing credentials and fails on first API call.

**What this locks in:**
- Databricks workspace as the execution environment
- `databricks.rag_eval` as the LLM routing layer
- `gpt-oss-120b` as the default alignment model (hardcoded in `dspy_utils.py:10`)

### Deferred / Open

None identified.

---

## DEC-013: Testing Strategy — Unit Tests with Full Mocking

**Status:** Decided
**Date:** 2025-08-24 (commit `443dd12`)
**Evidence:** `pytest.ini`, `tests/` directory (10 test files, ~3,400 lines)

### Context

The application depends on external services (MLflow, Databricks APIs, LLM endpoints) that are expensive and non-deterministic to call in tests.

### Options Considered

| Option | Evidence it was considered | Why not chosen (if known) |
|---|---|---|
| Unit tests with mocked external services | Current implementation | — (chosen) |

No evidence of integration testing or end-to-end testing considered.

### Decision

All tests use `unittest.TestCase` or `pytest` with extensive `unittest.mock.patch` decorators. Every MLflow call, Databricks SDK call, and LLM invocation is mocked. The test suite covers: Pydantic model validation (`test_models.py`), judge creation/evaluation/optimization (`test_instruction_judge.py`), all six service classes, and utility functions. `pytest.ini` defines three markers (`unit`, `integration`, `slow`) but no tests use the `integration` or `slow` markers.

No frontend tests exist. No end-to-end tests exist. The DSPy optimization loop is mocked — the `scorer_func.align()` call is stubbed, not executed.

### Consequences

**Accepted tradeoffs:**
- Tests cannot detect regressions in MLflow API compatibility (the most common breakage vector, per DEC-001).
- The DSPy alignment path — the core differentiating feature — is untested with real data. Tests verify the service orchestration but not whether SIMBA actually improves judge instructions.
- No frontend coverage means React component regressions are caught only by manual testing.

**What this locks in:**
- The mock-based test architecture means tests must be updated whenever MLflow or Databricks SDK APIs change their signatures.
- `pytest.ini` with `addopts = -v --tb=short --strict-markers --disable-warnings` — strict markers are enforced but `integration` and `slow` markers are unused.

### Deferred / Open

- `src/scripts/test.py:11` — `# TODO: Implement comprehensive test suite` — placeholder test runner script.

---

## DEC-014: Fork Purpose — Personal Fork of databricks-solutions/judge-builder

**Status:** Active
**Date:** 2025-08-19 (fork creation)
**Evidence:** `git remote -v` (origin: `alexxx-db/databricks-llm-judge-builder`), commit history shows all substantive commits by Samraj Moorjani (`@databricks.com` and `@gmail.com`)

### Context

This repo is a personal fork of `databricks-solutions/judge-builder`. The upstream is the canonical Databricks solutions repository.

### Options Considered

Not applicable — this is a fork configuration, not an architectural decision.

### Decision

The repo was initialized by `service-jira-pub-repo-auto` (`be60048`, 2025-08-19) with a skeleton (LICENSE, NOTICE, SECURITY, .gitignore, CODEOWNERS, README). All application code was authored from scratch in this fork by Samraj Moorjani. There is no upstream remote configured — the fork is the de facto origin. One tag exists: `judge-builder/v0.3.4` (2025-10-31). One commit by Alex Barreto (`79b53cc`, 2026-03-29, `CALIBRATION.md`).

### Consequences

**Accepted tradeoffs:**
- No upstream tracking means this fork cannot easily pull updates from `databricks-solutions/judge-builder` if the upstream evolves.
- The repo name (`databricks-llm-judge-builder`) differs from the upstream (`judge-builder`), which may cause confusion about the relationship.

**What this locks in:**
- This fork is self-contained. It shares no commit history with the upstream beyond the initialization skeleton.

### Deferred / Open

None identified.

---

## DEC-015: Node.js 18+ Version Requirement

**Status:** Decided
**Date:** 2025-08-24 (commit `443dd12`)
**Evidence:** `README.md:14` ("Node.js 18+"), `setup.sh:20-23`, `src/client/package.json`

### Context

The React frontend requires a Node.js runtime for development (Vite dev server) and build (Vite production build).

### Options Considered

| Option | Evidence it was considered | Why not chosen (if known) |
|---|---|---|
| Node.js 18+ | README requirement, `setup.sh` checks `command -v node` | — (chosen) |

No evidence of alternative versions or runtimes considered.

### Decision

Node.js 18+ is required. The constraint comes from Vite 5.x (`"vite": "^5.0.8"` in `package.json`) which requires Node.js ≥18.0.0. React 18.3.x does not itself require Node.js 18, but Vite's ESM-native architecture does. `setup.sh` checks for the `node` command but does not validate the version — it fails with a generic error if Node.js is missing.

### Consequences

**Accepted tradeoffs:**
- Node.js is not available on Databricks runtimes. The frontend can only be built on developer machines or CI, not within a Databricks workspace.

**What this locks in:**
- Vite 5.x as the build tool (requires Node.js 18+)
- npm as the package manager (no evidence of yarn or pnpm support)

### Deferred / Open

- `setup.sh` does not check Node.js version, only existence.

---

## DEC-016: Alignment as Prompt Optimization, Not Model Fine-Tuning

**Status:** Decided
**Date:** 2025-09-16 (commit `3e5e477`)
**Evidence:** `src/server/judges/custom_simba_optimizer.py:103` (`optimized_instructions = optimized_program.signature.instructions`), `src/server/judges/instruction_judge.py:124-151` (`optimize()`), `src/server/services/judge_service.py:182-221` (`create_new_version`)

### Context

Judges must be improvable based on human feedback. The improvement can happen at the prompt level (changing the instruction text) or the model level (fine-tuning the judge LLM).

### Options Considered

| Option | Evidence it was considered | Why not chosen (if known) |
|---|---|---|
| Prompt optimization via DSPy | Current implementation — optimizer output is `optimized_program.signature.instructions` (a string) | — (chosen) |
| Model fine-tuning | No evidence considered |

No evidence of alternatives considered.

### Decision

The boundary is explicit in the code: `CustomSIMBAAlignmentOptimizer.align()` returns a new `Judge` created by `make_judge(name, instructions=optimized_instructions, model=judge.model)` — the model is passed through unchanged, only the instructions change. The `create_new_version()` method stores the aligned instruction and increments the version counter. The judge model (`gpt-oss-120b` or a custom endpoint) is never modified.

The system does support bringing a custom model as the judge via `alignment_model_config` (commit `6349464`, `databricks:/endpoint-name` format). This model can be a pre-fine-tuned model, but the platform does not perform the fine-tuning.

### Consequences

**Accepted tradeoffs:**
- Prompt optimization has a ceiling. The judge instruction can only encode so much domain knowledge in text. For domains where the base LLM lacks fundamental understanding (e.g., clinical domain per `CALIBRATION.md`), prompt optimization alone may not close the agreement gap.
- Each alignment run produces a new instruction string, not a model artifact. There is no model versioning, no A/B testing of model weights, and no way to roll back a model change (only instruction rollback via version history in experiment tags).
- The alignment model (used for optimization) and the judge model (used at inference) can differ. The alignment runs through `AgentEvalLM` or LiteLLM, while the judge at inference runs through `make_judge()` which uses MLflow's internal routing.

**What this locks in:**
- Instruction text as the sole optimization artifact
- The alignment improvement is bounded by the base model's instruction-following capability
- No GPU or training infrastructure required for alignment — it is an API-only operation

### Deferred / Open

None identified.

---

## DEC-017: In-Memory Judge Storage with MLflow Tag Reconstruction

**Status:** Decided
**Date:** 2025-08-24 (commit `443dd12`)
**Evidence:** `src/server/services/judge_service.py:31-35` (`_judges`, `_versions` dicts), `judge_service.py:335-354` (`load_all_judges_on_startup`), `judge_service.py:224-278` (`_get_or_recreate_judge`)

### Context

Judge state (current instructions, version, labeling run ID, alignment config) must persist across user sessions but the application has no database.

### Options Considered

| Option | Evidence it was considered | Why not chosen (if known) |
|---|---|---|
| In-memory dicts + MLflow experiment tag reconstruction | Current implementation | — (chosen) |

No evidence of a database, Delta table, or other persistence layer considered.

### Decision

Judges are stored in Python dicts (`_judges: Dict[str, InstructionJudge]`, `_versions: Dict[str, Dict[int, InstructionJudge]]`). On startup, `load_all_judges_on_startup()` searches for MLflow experiments tagged with `judge_builder = 'true'`, reads the `judges` JSON tag, and reconstructs `InstructionJudge` instances. Judge metadata is serialized as a JSON blob in a single MLflow experiment tag.

### Consequences

**Accepted tradeoffs:**
- Application restart causes a cold start. All judges must be reconstructed from MLflow, which requires searching experiments and parsing JSON from tags. Startup time scales linearly with the number of judges.
- MLflow experiment tags have size limits. A JSON blob containing many judges with long instructions could exceed the tag value limit.
- In-memory storage means no horizontal scaling — two app instances would have divergent judge state.
- The `_get_or_recreate_judge` method at line 263 has a TODO indicating that optimized (aligned) instructions may not be correctly restored on reconstruction.

**What this locks in:**
- Single-instance deployment model
- MLflow experiment tags as the sole persistence layer
- JSON serialization of judge metadata (including `alignment_model_config`)

### Deferred / Open

- `src/server/services/judge_service.py:263` — `# TODO: We may need to recreate the judge with optimized instructions if needed`

---

## DEC-018: Background Task Alignment (Post-Timeout Fix)

**Status:** Decided
**Date:** 2025-10-18 (commit `c212f3f`)
**Evidence:** `src/server/routers/alignment.py:22-111`, `src/server/models.py:140-170` (`AlignmentStartResponse`, `AlignmentTaskStatus`)

### Context

Alignment runs take minutes to complete. The original synchronous endpoint caused HTTP timeouts in deployed environments where Databricks Apps has a request timeout.

### Options Considered

| Option | Evidence it was considered | Why not chosen (if known) |
|---|---|---|
| Synchronous HTTP response | Original implementation (replaced in `c212f3f`). PR #21 title: "Fix issue where alignment shows failure but runs in background" | Replaced — timed out in deployed Databricks Apps |
| FastAPI `BackgroundTasks` with polling | Current implementation | — (chosen) |

### Decision

Alignment was moved to FastAPI's `BackgroundTasks` with a start/poll pattern: `POST /{judge_id}/align` returns immediately with `AlignmentStartResponse`, and `GET /{judge_id}/align-status` is polled by the frontend. Status is tracked in a module-level dict (`alignment_status: dict[str, AlignmentTaskStatus]`). The frontend polls with exponential backoff (2s → 4s → 8s → 16s → 30s max, 20 attempts max).

### Consequences

**Accepted tradeoffs:**
- Module-level `alignment_status` dict means alignment state is lost on restart. If the app restarts during alignment, the task status becomes permanently "unknown."
- Only one alignment per judge can run at a time (409 Conflict if already running).
- Status is cleared after the first read (`del alignment_status[judge_id]` in the status endpoint). If the frontend misses the response, the result is lost.

**What this locks in:**
- Poll-based alignment status (no WebSockets, no SSE)
- Single-threaded alignment per judge
- The frontend's exponential backoff timing determines the user experience for alignment completion detection

### Deferred / Open

None identified.

---

## Decision Dependencies

| Decision | Depends On | Constrains |
|---|---|---|
| DEC-001 (DSPy SIMBA) | DEC-012 (Databricks workspace, `AgentEvalLM`) | DEC-016 (prompt optimization only), DEC-008 (alignment step) |
| DEC-002 (MLflow scorer delivery) | DEC-011 (`InstructionJudge` wraps `make_judge`) | DEC-008 (deploy step is automatic), DEC-010 (traces must be in MLflow) |
| DEC-003 (full-stack SPA) | DEC-004 (FastAPI backend) | DEC-005 (frontend tech stack), DEC-015 (Node.js requirement) |
| DEC-004 (FastAPI) | — | DEC-003 (OpenAPI → TS client), DEC-018 (BackgroundTasks) |
| DEC-005 (shadcn/ui) | DEC-003 (React SPA), DEC-015 (Node.js) | — |
| DEC-006 (uv) | — | DEC-007 (shell scripts call `uv run`) |
| DEC-007 (shell deploy) | DEC-006 (uv), DEC-012 (Databricks CLI) | — |
| DEC-008 (4-step workflow) | DEC-001 (alignment engine), DEC-009 (labels), DEC-002 (scorer delivery) | DEC-017 (state must persist across steps) |
| DEC-009 (managed evals labeling) | DEC-012 (Databricks workspace) | DEC-011 (binary/categorical schema), DEC-008 (label step) |
| DEC-010 (MLflow traces) | DEC-012 (Databricks workspace) | DEC-008 (example source) |
| DEC-011 (InstructionJudge) | DEC-002 (`make_judge` API) | DEC-016 (instruction is the optimization surface) |
| DEC-012 (Databricks integration) | — | DEC-001, DEC-002, DEC-009, DEC-010, DEC-017 |
| DEC-013 (test strategy) | — | — |
| DEC-014 (fork purpose) | — | — |
| DEC-015 (Node.js 18+) | DEC-003 (React SPA) | DEC-005 (Vite build) |
| DEC-016 (prompt optimization) | DEC-001 (SIMBA), DEC-011 (InstructionJudge) | — |
| DEC-017 (in-memory + MLflow tags) | DEC-012 (MLflow as persistence) | DEC-008 (state across workflow steps) |
| DEC-018 (background alignment) | DEC-004 (FastAPI BackgroundTasks) | DEC-008 (alignment step UX) |

---

## Deferred Decisions

Items where the code contains explicit TODOs, placeholder values, empty configuration, or no-op implementations that indicate a design choice not yet made.

| Item | Location | What needs deciding | Evidence |
|---|---|---|---|
| Optimized instruction restoration on restart | `src/server/services/judge_service.py:263` | Whether judges recreated from metadata should use the original or aligned instructions | `# TODO: We may need to recreate the judge with optimized instructions if needed` |
| Individual trace evaluation results | `src/server/services/alignment_service.py:90,141` | Whether `EvaluationResult.evaluation_results` should be populated with per-trace `JudgeTraceResult` objects | `evaluation_results=[]  # TODO: Implement individual trace results` |
| Dead optimizer constant | `src/server/utils/constants.py:8` | Whether `DEFAULT_JUDGE_OPTIMIZER = 'miprov2'` should be removed or updated to `'simba'` | Unreferenced in codebase; actual optimizer is SIMBA |
| `AgentEvalLM` parent class model string | `src/server/utils/dspy_utils.py:41` | Whether `'databricks/databricks-llama-4-maverick'` is the correct parent init value or a placeholder | Hardcoded string passed to `super().__init__()` regardless of actual model |
| `AgentEvalLM.load_state` | `src/server/utils/dspy_utils.py:50` | Whether DSPy state persistence should be implemented | `pass` (no-op) |
| Lifespan shutdown cleanup | `src/server/app.py:109` | Whether any cleanup is needed on application shutdown | `pass` comment: "Shutdown (if needed in the future)" |
| `JUDGE_OPTIMIZER` env var | `deploy.sh:98`, `src/app.yaml` | Whether the env var should be read by the server or removed from `app.yaml` | Written to `app.yaml` but never read by server code |
| Comprehensive test runner | `src/scripts/test.py:11` | Whether this script should be implemented or removed | `# TODO: Implement comprehensive test suite` |

---

## Fork Divergence from Upstream

**Upstream:** `databricks-solutions/judge-builder`
**Fork point:** `be60048` (2025-08-19), skeleton commit by `service-jira-pub-repo-auto`

### What this fork inherits unchanged

The initialization skeleton only: `LICENSE.md` (Databricks License), `NOTICE.md`, `SECURITY.md` (report to `security@databricks.com`), `CODEOWNERS.txt`, `.gitignore`, and an initial `README.md`. No application code was inherited.

### What this fork changes or extends

All application code was authored in this fork. The substantive commit history begins at `443dd12` (2025-08-24, "Initial commit to judge builder") — 5 days after the skeleton. This is not a modification of an upstream application; it is an original application built in a pre-configured repository.

One fork-specific commit by a non-Databricks author: `79b53cc` (2026-03-29, Alex Barreto, `CALIBRATION.md`).

### Alignment with upstream going forward

No upstream remote is configured. No merge commits reference an upstream. No commit messages mention syncing with upstream. The fork is operationally independent.
