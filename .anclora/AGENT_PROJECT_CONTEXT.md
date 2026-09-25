# Anclora CleanSheet — Agent Project Context

AGENT_PROJECT_CONTEXT_VERSION=2.0
STATUS=ACTIVE

## Identity

APPLICATION_NAME=Anclora CleanSheet
REPOSITORY=anclora-clearsheet
PROJECT_ROLE=Application (CSV/XLSX cleaning, recipes and scheduled automations)
PRODUCT_FAMILY=Anclora Group

This repository had no project-level `.anclora` contract at bootstrap time. These
files are the first repository-local declaration and remain subordinate to the
workspace policy and Toni's current instruction.

## Canonical QA Bootstrap

QA governance is inherited from:
[`../../ANCLORA_WORKSPACE_AGENT_POLICY.md`](../../ANCLORA_WORKSPACE_AGENT_POLICY.md)

Default:
`QA_MODE=AUTO`

Before planning verification, classify:
- `FAST`
- `STANDARD`
- `FULL`

Task-level historical QA boilerplate does not override workspace QA classification.
Only explicit mission tokens change the mode:
- `QA_OVERRIDE=FAST`
- `QA_OVERRIDE=STANDARD`
- `QA_OVERRIDE=FULL`

Testing, lint, and build execution must follow the workspace batched execution cadence:
no repeated gates per micro-edit, and no rerun of unchanged successful gates without invalidation.
Repository-specific runtime minima are defined in [`PRODUCTION_RUNTIME.md`](PRODUCTION_RUNTIME.md).

## Architecture and routing

| Domain | Source of truth |
| --- | --- |
| Product behavior | `README.md`, `memory/PRD.md`, frontend and backend tests |
| HTTP/API surface | `backend/server.py`, `backend/routes/` |
| Persistence | `backend/models.py` and `DATABASE_URL` |
| File storage | `backend/storage.py`, `backend/connectors/` |
| Deterministic processing | `backend/engine.py`, `backend/recipe_service.py`, `backend/heuristics.py` |
| Scheduling | `backend/scheduler_worker.py`, `backend/scheduler_dispatcher.py`, `backend/scheduler_utils.py` |
| Frontend | `frontend/src/`, CRA/CRACO scripts in `frontend/package.json` |
| Delivery checks | `.github/workflows/ci.yml`, `.github/workflows/main-baseline.yml` |

## Non-negotiable invariants

- Preserve existing `/api` routes and frontend API contracts unless a task explicitly changes them.
- Never print, commit, or expose secrets, cookies, tokens, connection strings, or uploaded file contents.
- Keep `backend/.env` and `frontend/.env` local-only with mode `0600`; commit only `.env.example` files.
- Do not add product behavior, database migrations, seed data, or destructive cleanup as part of governance bootstrap.
- QA identities must be dedicated test identities; no personal account is a QA account.
- Keep the contractual branch flow `development -> staging -> production -> main`; never force-push.

## Known bootstrap gaps

- No repository-local agent instructions existed before this bootstrap.
- No migration framework is present; the current model initializes tables with SQLAlchemy `create_all`.
- No dedicated QA account contract or browser QA harness is present in this repository.
- The runtime can use configured PostgreSQL via `DATABASE_URL`, but the checked-in code defaults to SQLite when unset.
