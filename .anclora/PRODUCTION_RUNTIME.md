# Anclora CleanSheet — Production Runtime Contract

PRODUCTION_RUNTIME_MANIFEST_VERSION=2.0
STATUS=PRODUCTION_BACKED

## Deployment infrastructure

VERCEL_PROJECT_NAME=anclora-clearsheet
VERCEL_PROJECT_ID=prj_ZMw3lbQoxDjeeNwsisQ3jWDNgtsu
VERCEL_ROOT_DIRECTORY=frontend
VERCEL_FRAMEWORK=create-react-app
VERCEL_PRODUCTION_BRANCH=main
GITHUB_DEFAULT_BRANCH=development
PRODUCTION_DOMAIN=clearsheet.anclora.com
DNS_PROVIDER=Hostinger
DNS_STATUS=CONFIGURED_TLS_PENDING
BACKEND_RUNTIME_EXTERNAL_REQUIRED=true
BACKEND_RUNTIME_PROVIDER=Contabo VPS
BACKEND_RUNTIME_CONTAINERIZED=true
BACKEND_REVERSE_PROXY=Caddy
BACKEND_DEPLOY_SOURCE=main
BACKEND_DEPLOY_MODEL=Docker image pinned by SHA
BACKEND_PRODUCTION_URL=https://api.cleansheet.anclora.com
SCHEDULER_RUNTIME=SEPARATE_CONTAINER
SCHEDULER_REPLICAS=1
NEON_RESOURCE_NAME=anclora-clearsheet-db
NEON_RESOURCE_ID=store_AyigyfkTetw3n9wA
DATABASE_PROVIDER=Neon PostgreSQL
DATABASE_RUNTIME_SCOPE=production
LOCAL_RUNTIME_MODEL=PRODUCTION_BACKED

The Vercel project is frontend-only (`frontend/`). The FastAPI backend remains an
external runtime and must be exposed through `REACT_APP_BACKEND_URL` before a
production deployment is considered functional. Human local development and QA
use the same Production Neon database. SQLite remains available only for
deterministic isolated tests where already configured. DNS remains authoritative
at Hostinger.

## Runtime topology

```text
React CRA/CRACO frontend -> FastAPI backend -> SQLAlchemy -> DATABASE_URL (PostgreSQL in hosted runtime)
                                                     -> SQLite fallback when DATABASE_URL is unset
                                      -> Vercel Blob or local temporary storage
                                      -> optional Redis-backed rate limiting
                                      -> optional S3-compatible connectors
```

`LOCAL_RUNTIME_MODEL=PRODUCTION_BACKED`: human local development and QA provide
`DATABASE_URL` pointing to the Production Neon database. The current code still
has a SQLite fallback when the variable is absent; that fallback is reserved for
isolated deterministic tests and is not the human development runtime.

## Database and migrations

DATABASE_PROVIDER=Neon PostgreSQL
ORM=SQLAlchemy 2.x
MIGRATION_SYSTEM=Alembic
PRODUCTION_MIGRATIONS_ALLOWED=false
MIGRATION_CONFIRMATION_REQUIRED=true

`backend/models.py` permits `create_all` only for SQLite isolated tests. PostgreSQL
startup rejects implicit schema creation; production schema is managed by Alembic
revision `0001_initial_schema`.

## Environment contract

Backend names observed in code:

`DATABASE_URL`, `FRONTEND_URL`, `JWT_SECRET`, `CLEANSHEET_MASTER_KEY`,
`BLOB_READ_WRITE_TOKEN`, `S3_BUCKET`, `REDIS_URL`,
`AUTH_ADMIN_EMAILS`, `AUTH_WHITELIST_TOKEN_TTL_HOURS`, `AUTH_PASSWORD_MIN_LENGTH`.

Frontend names observed in code:

`REACT_APP_BACKEND_URL`, `ENABLE_HEALTH_CHECK`.

The exact names and safe placeholders are maintained in `backend/.env.example`
and `frontend/.env.example`. Secrets belong only in deployment configuration or
local ignored files. Never print their values.

## QA and operations

QA_POLICY=WORKSPACE_PROPORTIONAL
QA_MODE_DEFAULT=AUTO
FAST_TARGETED_TESTING_POLICY=MINIMUM_SUFFICIENT_SET
FAST_FULL_TEST_SUITE_ALLOWED=false
STOP_WHEN_SUFFICIENT_EVIDENCE=true
TEST_EXECUTION_POLICY=BATCHED
FULL_GATES_AFTER_EVERY_EDIT=false
REPEAT_UNCHANGED_SUCCESSFUL_GATES=false
VISUAL_QA_EXECUTION=BY_QA_MODE

TOKEN_ECONOMY_POLICY=ADAPTIVE
CAVEMAN_MODE_DEFAULT=AUTO
CAVEMAN_GRANULARITY=TASK
QA_MINIMUM_FOR_DATABASE_MIGRATION=FULL
QA_MINIMUM_FOR_AUTH=FULL
QA_MINIMUM_FOR_RELEASE_PROMOTION=FULL


QA_AUTH_MODEL=DEDICATED_USER
QA_USER_EMAIL=qa.cleansheet@anclora.local
QA_DELETE_AFTER_TEST=false
VISUAL_QA_EXECUTION=BY_QA_MODE

This bootstrap contains no production migration, data mutation, deployment, or
personal-account test activity.
