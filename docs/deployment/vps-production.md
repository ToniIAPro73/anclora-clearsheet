# CleanSheet VPS production

CleanSheet runs as two containers from the same
`anclora/cleansheet-backend:<main-sha>` image:

- API on loopback port 8102, exposed through `https://api.cleansheet.anclora.com`.
- One scheduler worker with no public port.

Both processes use the external runtime file
`/home/toni/.config/anclora/runtime/cleansheet.env`. PostgreSQL schema changes
are owned by Alembic; application and scheduler startup perform connectivity
checks only and never run DDL. The scheduler is intentionally single-instance.
