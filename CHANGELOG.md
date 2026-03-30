# Changelog

**Repository:** `databricks-llm-judge-builder`
**Forked from:** [`databricks-solutions/judge-builder`](https://github.com/databricks-solutions/judge-builder)
**Stack:** FastAPI (Python) · React/TypeScript · DSPy · MLflow 3.x · Databricks SDK

**Branches covered:** `main`, `marketplace`, `judge-builder-v0.3.4`, `judge-builder-v0.3.3`, `judge-builder-v0.3.2`, `v0.3.2-release-notes`, `fix-alignment-timeout`, `fix-duplicate-trace`, `fix-path-vulnerability`, `fix-temp`, `remove-alignment-selector`
**Commit range:** 2025-08-19 → 2026-03-29
**Total commits:** 88 (all branches)
**Contributors:** Samraj Moorjani (86 commits), Alex Barreto (1 commit), service-jira-pub-repo-auto (1 commit)

> **Format:** Version-tagged sections derived from git tags and the existing
> CHANGELOG entries. No version tags exist before `judge-builder/v0.3.4`
> (2025-10-31), so earlier versions are derived from the version bump commits
> and PR merge points visible in the git history.

> **Fork baseline:** The repo was initialized by `service-jira-pub-repo-auto`
> (`be60048`, 2025-08-19) with a skeleton (LICENSE, NOTICE, SECURITY, .gitignore,
> CODEOWNERS, README). All substantive code was authored in this repo by
> Samraj Moorjani. There is no upstream commit history to exclude.

---

## [Unreleased]

### Infrastructure & DX

- **Added** `CALIBRATION.md` documenting human-LLM judge agreement rates, systematic failure modes, and DSPy alignment effect across domains. (`79b53cc`, 2026-03-29)

### Backend (Python/FastAPI)

- **Fixed** `uv run` project discovery after `src/` directory restructure — added `--project src` to all `uv run` invocations and updated module paths (`src.server.app` → `server.app`). (`e298264`, 2026-02-10)

### Infrastructure & DX

- **Refactored** Repository directory structure for Databricks Marketplace publishing — moved all source code under `src/` (`server/` → `src/server/`, `client/` → `src/client/`, `dev/` → `src/dev/`, `scripts/` → `src/scripts/`), updated `setup.sh` and `deploy.sh` paths, added `README-DEV.md`, removed stale `.pyc` files and `dev-requirements.txt`. (`1c911ca`, 2025-10-31) ⚠️ Breaking change — all file paths shifted under `src/`

---

## [0.3.4] – 2025-10-28

*Tag: `judge-builder/v0.3.4`*

### Backend (Python/FastAPI)

- **Fixed** Path traversal vulnerability in static file serving — resolved path is now validated to be within `client/build/` before serving. (`d620fa5`, 2025-10-28) 🔒 Security
- **Changed** CORS middleware to only load in development mode, controlled by `DEPLOYMENT_MODE` environment variable. Previously loaded unconditionally. (`d620fa5`, 2025-10-28) 🔒 Security

### Infrastructure & DX

- **Changed** Version bump to 0.3.4 in `pyproject.toml` and `package.json`, updated `CHANGELOG.md` with release notes. (`617d3dc`, 2025-10-28)
- **Changed** `dev/watch.sh` updated with revised port and process management. (`d620fa5`, 2025-10-28)

---

## [0.3.3] – 2025-10-18

### Backend (Python/FastAPI)

- **Changed** Alignment execution from synchronous HTTP response to background task with polling — added `POST /api/alignment/start` returning a task ID and `GET /api/alignment/status/{task_id}` for polling. Previous `AlignmentResponse` model replaced with `AlignmentStartResponse`. (`c212f3f`, 2025-10-18) ⚠️ Breaking change — alignment API contract changed 📐 Schema change
  - New Pydantic models: `AlignmentStartResponse`, alignment status polling models in `server/models.py`
  - `server/routers/alignment.py`: +95 lines, two new endpoints
  - `server/judges/instruction_judge.py`: evaluation flow changes to support async alignment
- **Fixed** Alignment timeout in deployed environments — alignment previously failed with HTTP timeout before completing. Background task pattern eliminates this. (`c212f3f`, 2025-10-18)
- **Fixed** Additional alignment polling edge cases — error handling for status endpoint, requirement version bump for `databricks-agents`. (`777250f`, 2025-10-18)

### Frontend (React/TypeScript)

- **Changed** Alignment UI flow from single request/response to start-then-poll pattern — `useApi.ts` hook updated with polling logic for alignment task status. (`c212f3f`, 2025-10-18) 🔌 Integration point
  - `AlignmentResponse.ts` model deleted, replaced by `AlignmentStartResponse.ts`
  - `AlignmentService.ts` and `ApiService.ts` updated for new endpoints
  - `useApi.ts`: rewritten alignment invocation (~110 lines changed)
- **Fixed** Frontend polling guard added to prevent stale state when navigating away during alignment. (`777250f`, 2025-10-18)

### Infrastructure & DX

- **Deps** `databricks-agents` version requirement updated in `requirements.txt`. (`777250f`, 2025-10-18)

---

## [0.3.2] – 2025-10-17

### Backend (Python/FastAPI)

- **Fixed** Duplicate traces being added to labeling sessions — `labeling_service.py` now deduplicates before insertion (+35 lines). (`4286fe1`, 2025-10-17)
- **Fixed** Aligned instruction not propagating correctly to new judge versions — `instruction_judge.py` and `judge_service.py` simplified to fix version chaining. (`4286fe1`, 2025-10-17) 🧪 Evaluation change
- **Changed** Default alignment model back to Databricks-hosted endpoint (`gpt-oss-120b` via `AgentEvalLM`) instead of user-configured serving endpoint. (`424ebfe`, 2025-10-17) 🔌 Integration point
- **Removed** Alignment model selector from judge creation page — selection now happens only on the judge detail page. (`9d757b4`, 2025-10-17)

### Frontend (React/TypeScript)

- **Removed** `AlignmentModelSelector` component from `WelcomePage.tsx` (judge creation form). Alignment model selection retained only on `JudgeDetailPage.tsx`. (`9d757b4`, 2025-10-17)

### Infrastructure & DX

- **Changed** Version bump to 0.3.2, release notes added to `CHANGELOG.md`. (`05742df`, 2025-10-17)
- **Deps** `databricks-agents` bumped to `>=1.8.0` in `pyproject.toml`. (`05742df`, 2025-10-17) 🔌 Integration point

---

## [0.3.1] – 2025-10-09

### Backend (Python/FastAPI)

- **Added** Monkey patch for `mlflow.genai.judges.utils.call_chat_completions` to set custom client name `judge-builder-v{VERSION}` via `databricks.rag_eval` context — enables tracking of judge builder requests in telemetry. (`25f5847`, 2025-10-08) 🔌 Integration point
  - Patch applied in `server/app.py` at startup (+35 lines)
  - `server/judges/custom_simba_optimizer.py` deleted — client name patching moved to app-level monkey patch

### Infrastructure & DX

- **Changed** Version bump to 0.3.1 in `pyproject.toml` and `package.json`. (`03a490a`, 2025-10-09)

---

## [0.3.0] – 2025-10-03

### Judge Engine

- **Added** Alignment model separation — DSPy alignment can now use a different model than judge evaluation via user-configurable Databricks serving endpoints. (`6349464`, 2025-09-30) 🔌 Integration point 🧪 Evaluation change
  - New `CustomSIMBAAlignmentOptimizer` extending MLflow's `SIMBAAlignmentOptimizer` (`server/judges/custom_simba_optimizer.py`)
  - `InstructionJudge.optimize()` accepts optional `alignment_model` parameter
  - Model format: `databricks:/endpoint-name` via LiteLLM
  - Backward compatible: existing judges use default `AgentEvalLM`
  - New dependency: `databricks-dspy`
- **Fixed** Iterative alignments not evaluating full set of traces — cached results from prior alignment version were reused incorrectly, causing evaluation to run on a subset. (`7001ed7`, 2025-10-03) 🧪 Evaluation change
  - `alignment_service.py`: dataset version tracking fixed
  - `cache_service.py`: cache key generation corrected

### Backend (Python/FastAPI)

- **Added** `ServingEndpointService` with 5-minute TTL caching for listing Databricks serving endpoints. (`6349464`, 2025-09-30)
- **Added** `GET /api/serving-endpoints` router for frontend endpoint discovery. (`6349464`, 2025-09-30)
- **Added** `AlignmentModelConfig` and `ServingEndpointConfig` Pydantic models. (`6349464`, 2025-09-30) 📐 Schema change
- **Added** `GET /api/judges/{id}/alignment-model` and `PUT /api/judges/{id}/alignment-model` endpoints for persisting per-judge alignment model config. (`61e3371`, 2025-10-02)
- **Changed** Reduced logging verbosity across all services — `print()` calls replaced with `logging.info()`/`logging.debug()`, Databricks SDK and urllib3 loggers silenced. (`7b0c1ac`, 2025-10-02)

### Frontend (React/TypeScript)

- **Added** `AlignmentModelSelector` component — dropdown for selecting Databricks serving endpoints as alignment model, with search, loading states, and current-selection display. (`bbc521d`, 2025-10-01)
  - New TS models: `AlignmentModelConfig.ts`, `ServingEndpointConfig.ts`
  - New service: `ServingEndpointsService.ts`
  - `ApiService.ts`: +63 lines for alignment model CRUD
- **Changed** `JudgeDetailPage.tsx` — added alignment model selector panel, persist model selection to backend, display current model in alignment section. (`61e3371`, 2025-10-02)
  - `JudgesService.ts`: +26 lines for alignment model endpoints
- **Changed** Alignment limit messaging — `JudgeDetailPage.tsx` now shows clear minimum-example requirement (10 labeled traces) with `SchemaInfo` model. (`ad2429c`, 2025-10-02)

### Infrastructure & DX

- **Fixed** `dev/watch.sh` process management and port detection. (`7b0c1ac`, 2025-10-02)
- **Changed** Version bump to 0.3.0 in `pyproject.toml` and `package.json`. (`c2ede30`, 2025-10-03)

---

## [0.2.1] – 2025-09-24

### Backend (Python/FastAPI)

- **Added** Caching decorator for `schema_analysis.py` — output type inference results cached to avoid repeated LLM calls during labeling sessions. (`4c6fc24`, 2025-09-24)

---

## [0.2.0] – 2025-09-23

### Judge Engine

- **Changed** Judge implementation replaced: `CustomPromptJudge` + `CustomPromptOptimizer` deleted, replaced by `InstructionJudge` wrapping MLflow's `make_judge()` and `align()` APIs. (`3e5e477`, 2025-09-16) ⚠️ Breaking change 🔌 Integration point
  - Deleted: `server/judges/custom_prompt_judge.py`, `server/optimizers/custom_prompt_optimizer.py`, `server/optimizers/__init__.py`
  - Added: `server/judges/instruction_judge.py` (107 lines) — wraps `mlflow.genai.judges.make_judge()` for scorer creation and uses `mlflow.genai.judges.align()` for DSPy SIMBA optimization
  - Tests rewritten: `test_custom_prompt_judge.py` → `test_instruction_judge.py` (299 lines)
  - Dependencies: `mlflow[databricks]>=3.4.0`, `databricks-agents>=1.1.0` added to `pyproject.toml`
- **Added** Support for judges over expectations/traces (e.g., correctness judges) — extends beyond original request/response-only evaluation. (`3e5e477`, 2025-09-16)
- **Added** Arbitrary categorical output support — judge outputs no longer limited to binary pass/fail. Schema analysis infers categorical options from judge instructions. (`4f6eb82`, 2025-09-22) 📐 Schema change
  - New: `server/utils/schema_analysis.py` (91 lines) — `extract_categorical_options_from_instruction()` detects output schemas
  - New: `tests/test_judge_response_schema.py`, `tests/utils/test_schema_analysis.py` (198 lines total)
  - `server/models.py`: `SchemaInfo` model added
  - `alignment_service.py`, `judge_service.py`, `labeling_service.py`: updated to use inferred schemas

### Frontend (React/TypeScript)

- **Added** `JudgeInstructionInput` component — rich text input for judge instructions with template variable insertion buttons and validation. (`1747494`, 2025-09-19)
  - New: `components/JudgeInstructionInput.tsx` (137 lines)
  - New: `components/TemplateVariableButtons.tsx` (117 lines) — buttons for inserting MLflow template variables (`{{request}}`, `{{response}}`, `{{expected_response}}`, etc.)
  - New: `lib/templateValidation.ts` (101 lines) — validates template variable syntax in judge instructions
- **Added** Correctness judge template with proper MLflow template variable format (`{{request}}`, `{{expected_response}}`). (`77c0bc6`, 2025-09-19)
- **Changed** `WelcomePage.tsx` judge creation form — replaced plain textarea with `JudgeInstructionInput` component, added template variable buttons. (`1747494`, 2025-09-19)
- **Changed** `JudgeDetailPage.tsx` — updated labeling UI to support multi-class categorical labels (not just pass/fail), dynamic column rendering based on inferred schema. (`4f6eb82`, 2025-09-22)

### Backend (Python/FastAPI)

- **Changed** `alignment_service.py` refactored for `InstructionJudge` API — alignment now calls `judge.optimize()` directly instead of managing DSPy program lifecycle. (`3e5e477`, 2025-09-16)
- **Changed** `judge_service.py` simplified — scorer registration delegates to `InstructionJudge.register_scorer()`. (`3e5e477`, 2025-09-16)
- **Changed** `base_service.py` updated with workspace client initialization changes. (`4f6eb82`, 2025-09-22)

### Testing

- **Added** `tests/judges/test_instruction_judge.py` — 299-line test suite for `InstructionJudge` evaluate, optimize, and register_scorer flows. (`3e5e477`, 2025-09-16)
- **Removed** `tests/judges/test_custom_prompt_judge.py` — deleted with `CustomPromptJudge`. (`3e5e477`, 2025-09-16)
- **Added** `tests/test_judge_response_schema.py` and `tests/utils/test_schema_analysis.py` — schema inference tests. (`4f6eb82`, 2025-09-22)
- **Changed** `tests/services/test_alignment_service.py` — updated for `InstructionJudge` API. (`3e5e477`, 2025-09-16)

### Infrastructure & DX

- **Changed** Version bump to 0.2.0 in `pyproject.toml` and `package.json`. (`307932d`, 2025-09-23)
- **Deps** `mlflow[databricks]>=3.4.0` and `databricks-agents>=1.1.0` added. (`3e5e477`, 2025-09-16) 🔌 Integration point

---

## [0.1.0] – 2025-08-26

*Initial release of Judge Builder.*

### Judge Engine

- **Added** `CustomPromptJudge` — initial judge implementation with DSPy-based prompt optimization via `CustomPromptOptimizer`. (`443dd12`, 2025-08-24)
  - `server/judges/custom_prompt_judge.py`: judge evaluation using DSPy `ChainOfThought` programs
  - `server/optimizers/custom_prompt_optimizer.py`: DSPy MIPROv2 optimization loop with agreement metric
  - `server/utils/dspy_utils.py`: DSPy example conversion from MLflow traces
- **Fixed** Alignment not using fresh traces — optimizer was reusing stale trace data from prior runs. (`2ce3b96`, 2025-08-26)
- **Fixed** Alignment performance — reduced unnecessary DSPy program reinitialization in optimizer loop. (`92e804b`, 2025-08-26)

### Backend (Python/FastAPI)

- **Added** FastAPI application with router-service architecture. (`443dd12`, 2025-08-24)
  - Routers: `alignment.py`, `cache.py`, `experiments.py`, `judge_builders.py`, `judges.py`, `labeling.py`, `users.py`
  - Services: `alignment_service.py`, `base_service.py`, `cache_service.py`, `experiment_service.py`, `judge_builder_service.py`, `judge_service.py`, `labeling_service.py`, `user_service.py`
  - Models: `server/models.py` — Pydantic request/response schemas for all endpoints
  - Utilities: `constants.py`, `dspy_utils.py`, `naming_utils.py`, `parsing_utils.py`
- **Added** `server/prompts.py` — prompt templates for judge evaluation. (`3e3781f`, 2025-08-25)
- **Added** Static file serving — FastAPI serves React build from `client/build/` with SPA fallback routing. (`443dd12`, 2025-08-24)
- **Added** CORS middleware for development mode. (`443dd12`, 2025-08-24)
- **Added** `/health` endpoint. (`443dd12`, 2025-08-24)

### Frontend (React/TypeScript)

- **Added** React 18 SPA with Vite, TypeScript, Tailwind CSS, and shadcn/ui (Radix primitives). (`443dd12`, 2025-08-24)
- **Added** `WelcomePage.tsx` — judge creation form with name, instruction, experiment ID, and SME email input. (`443dd12`, 2025-08-24)
- **Added** `JudgeDetailPage.tsx` — judge detail view with tabbed sections for examples/traces, labeling, and alignment results. (`443dd12`, 2025-08-24)
- **Added** `ExperimentSelector` component — searchable dropdown for MLflow experiments. (`443dd12`, 2025-08-24)
- **Added** Auto-generated TypeScript API client in `fastapi_client/` from OpenAPI spec. (`443dd12`, 2025-08-24)
  - Services: `AlignmentService.ts`, `ApiService.ts`, `CacheService.ts`, `ExperimentsService.ts`, `JudgeBuildersService.ts`, `JudgesService.ts`, `LabelingService.ts`, `UsersService.ts`
- **Added** `useApi` hook — centralized API call management with loading states, error handling, and toast notifications. (`443dd12`, 2025-08-24)
- **Added** Toast notification system via `ToastContext` and Radix toast primitives. (`443dd12`, 2025-08-24)
- **Changed** UI/UX improvements from bug bash — expanded `JudgeDetailPage` with version comparison indicators, alignment metrics display, improved layout for labeling workflow. (`849e3cd`, 2025-08-25)
  - `JudgeDetailPage.tsx`: +217 lines (agreement/disagreement indicators, filtering)
  - `WelcomePage.tsx`: layout and validation improvements
  - `useApi.ts`: added user info fetching
  - `UserInfo.ts` model: added to fastapi_client
- **Added** `DefaultService.ts` — health check and base path resolution for deployed environments. (`3e3781f`, 2025-08-25)

### Infrastructure & DX

- **Added** `setup.sh` — interactive setup script: installs `uv`, creates `.venv` with Python 3.11, installs Python and Node dependencies, configures Databricks CLI profile and app name in `src/.env.local`, tests workspace connection. (`443dd12`, 2025-08-24)
- **Added** `deploy.sh` — deployment script: builds frontend, generates `requirements.txt` from `pyproject.toml`, creates `app.yaml`, syncs source to Databricks workspace via `databricks sync`, creates/deploys Databricks App. (`443dd12`, 2025-08-24)
- **Added** `dev/watch.sh` — development server script: starts FastAPI on `:8000` and Vite on `:5173`, auto-regenerates TypeScript client on server code changes via `watchmedo`, handles Databricks auth, cleanup on exit. (`443dd12`, 2025-08-24)
- **Added** `scripts/make_fastapi_client.py` — generates TypeScript API client from FastAPI OpenAPI spec. (`3e3781f`, 2025-08-25)
- **Added** `scripts/generate_semver_requirements.py` — converts `pyproject.toml` dependencies to pinned `requirements.txt` for deployment. (`443dd12`, 2025-08-24)
- **Added** `pytest.ini` with test markers: `unit`, `integration`, `slow`. (`443dd12`, 2025-08-24)
- **Added** Initial `CHANGELOG.md`. (`4f91652`, 2025-08-26)
- **Added** `README.md` with installation instructions, usage workflow, and license table. (`02d66f0`, 2025-08-24)
- **Fixed** `setup.sh` `sed` command compatibility issue. (2 commits: `dc0490d`, `4e72ba9`, 2025-09-02)
- **Fixed** Version management typo. (`5294bd9`, 2025-09-03)
- **Removed** Accidentally committed `client/node_modules/` directory. (`50e3545`, 2025-08-26)

### Testing

- **Added** Full test suite. (`443dd12`, 2025-08-24)
  - `tests/judges/test_custom_prompt_judge.py` (238 lines)
  - `tests/services/test_alignment_service.py` (219 lines)
  - `tests/services/test_cache_service.py` (250 lines)
  - `tests/services/test_experiment_service.py` (245 lines)
  - `tests/services/test_judge_builder_service.py` (327 lines)
  - `tests/services/test_judge_service.py` (344 lines)
  - `tests/services/test_labeling_service.py` (522 lines)
  - `tests/test_models.py` (430 lines)
  - `tests/utils/test_naming_utils.py` (176 lines)
  - `tests/utils/test_parsing_utils.py` (481 lines)

---

## Repository Stats

| Metric | Value |
|---|---|
| Total commits (all branches) | 88 |
| Non-merge commits | 60 |
| Commit range | 2025-08-19 – 2026-03-29 |
| Contributors | 3 |
| Most active contributor | Samraj Moorjani: 86 commits |
| Most-changed file | `pyproject.toml`: 13 commits |
| Second most-changed file | `server/services/alignment_service.py`: 12 commits |
| Third most-changed file | `client/src/pages/JudgeDetailPage.tsx`: 11 commits |
| Largest commit (by files) | `443dd12`: Initial commit (11,469 files, +2,129,464 lines — includes `node_modules`) |
| Largest commit (meaningful) | `1c911ca`: Marketplace restructure (134 files, +5,503 / −107 lines) |
| Python files with history | 96 |
| TypeScript/TSX files with history | 137 (excluding `node_modules`) |
| Dependency update commits | 18 |
| Test-related commits | 7 |
| Version tags | 1 (`judge-builder/v0.3.4`) |
| Branches (remote) | 11 |
