# Anclora CleanSheet — Production Runtime Contract

PRODUCTION_RUNTIME_MANIFEST_VERSION=1.0
STATUS=BOOTSTRAP_DECLARED

## Runtime topology

```text
React CRA/CRACO frontend -> FastAPI backend -> SQLAlchemy -> DATABASE_URL (PostgreSQL in hosted runtime)
                                                     -> SQLite fallback when DATABASE_URL is unset
                                      -> Vercel Blob or local temporary storage
                                      -> optional Redis-backed rate limiting
                                      -> optional S3-compatible connectors
```

`LOCAL_RUNTIME_MODEL=CONFIGURABLE`: the current code reads `DATABASE_URL` and
falls back to the tracked SQLite path `backend/cleansheet.db` when it is absent.
Production must provide its managed database URL; this bootstrap does not create
or migrate a database.

## Database and migrations

DATABASE_PROVIDER=CONFIGURED_BY_DATABASE_URL
ORM=SQLAlchemy 2.x
MIGRATION_SYSTEM=NONE_DECLARED
PRODUCTION_MIGRATIONS_ALLOWED=false
MIGRATION_CONFIRMATION_REQUIRED=true

`backend/models.py` currently calls `Base.metadata.create_all`. No production
migration is authorized or introduced by this bootstrap. Any future schema change
needs an explicit migration design and review before production execution.

## Environment contract

Backend names observed in code:

`DATABASE_URL`, `FRONTEND_URL`, `JWT_SECRET`, `CLEANSHEET_MASTER_KEY`,
`BLOB_READ_WRITE_TOKEN`, `S3_BUCKET`, `REDIS_URL`.

Frontend names observed in code:

`REACT_APP_BACKEND_URL`, `ENABLE_HEALTH_CHECK`, `DISABLE_EMERGENT_OVERLAY`.

The exact names and safe placeholders are maintained in `backend/.env.example`
and `frontend/.env.example`. Secrets belong only in deployment configuration or
local ignored files. Never print their values.

## QA and operations

QA_AUTH_MODEL=NOT_DECLARED
QA_DELETE_AFTER_TEST=NOT_DECLARED
VISUAL_QA_REQUIRED_FOR_UI_CHANGES=true

This bootstrap contains no production migration, data mutation, deployment, or
personal-account test activity.
