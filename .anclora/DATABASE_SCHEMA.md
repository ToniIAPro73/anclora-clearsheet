# CleanSheet production database

Provider: Neon PostgreSQL. Production schema is governed by Alembic revisions
`0001_initial_schema` and `0002_closed_access_whitelist`; PostgreSQL startup refuses
implicit `create_all`. SQLite `create_all` remains available only for isolated CI tests.

| Table | Purpose | Sensitivity |
|---|---|---|
| `users` | Application identities (`status`: active, disabled) | email, password hash |
| `auth_whitelist` | Invitation tokens (SHA-256 hashes), status, expiry | email, token hash (no raw secrets) |
| `auth_audit_events` | Security and access audit trail | event, email, metadata |
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
