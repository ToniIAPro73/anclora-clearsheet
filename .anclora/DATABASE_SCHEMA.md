# CleanSheet production database

Provider: Neon PostgreSQL. Production schema is owned by Alembic revision
`0001_initial_schema`; PostgreSQL startup refuses implicit `create_all`. SQLite
`create_all` remains available only for isolated CI tests.

| Table | Purpose | Sensitivity |
|---|---|---|
| `users` | Application identities | email, password hash |
| `source_files` | Source metadata and storage references | filenames, paths |
| `recipes` | Transformation definitions | user-authored definitions |
| `executions` | Run status and metrics | filenames, references |
| `automation_webhooks` | Webhook credentials | tokens, encrypted secrets |
| `processed_nonces` | Anti-replay keys | request identifiers |
| `external_storage_connections` | Encrypted connectors | encrypted credentials |
| `scheduled_automations` | Schedules and lease state | selectors |
| `scheduled_runs` | Scheduler audit | keys, errors |
| `alembic_version` | Migration state | none |

Persisted instants are timezone-aware; `timezone_name` is explicit IANA
metadata. QA identity: `qa.cleansheet@anclora.local`; no personal QA accounts.
